use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::Value;
use std::env;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::fs::{FileTypeExt, PermissionsExt};
use std::os::unix::net::{UnixListener, UnixStream};
use std::process::{Command, Stdio};
use std::sync::mpsc::{self, SyncSender, TrySendError};
use std::sync::{Arc, Mutex};
use std::thread;

const DEFAULT_SOCKET: &str = "/run/nyxd.sock";

#[derive(Serialize)]
struct Event {
    ts: String,
    source: String,
    severity: &'static str,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    suggested_action: Option<String>,
}

type Subscribers = Arc<Mutex<Vec<SyncSender<String>>>>;

fn event_from_journal(line: &str) -> Option<Event> {
    let record: Value = serde_json::from_str(line).ok()?;
    let priority: u8 = record.get("PRIORITY")?.as_str()?.parse().ok()?;
    if priority > 3 {
        return None;
    }
    let micros: i64 = record
        .get("__REALTIME_TIMESTAMP")?
        .as_str()?
        .parse()
        .ok()?;
    let timestamp = DateTime::<Utc>::from_timestamp_micros(micros)?;
    let message = record.get("MESSAGE")?.as_str()?.to_owned();
    let source = record
        .get("_SYSTEMD_UNIT")
        .or_else(|| record.get("_COMM"))
        .and_then(Value::as_str)
        .unwrap_or("system journal")
        .to_owned();
    let severity = match priority {
        0..=2 => "critical",
        _ => "error",
    };
    Some(Event {
        ts: timestamp.to_rfc3339(),
        source,
        severity,
        message,
        suggested_action: None,
    })
}

fn publish(subscribers: &Subscribers, event: &Event) {
    let Ok(serialized) = serde_json::to_string(event) else {
        eprintln!("nyxd: failed to encode journal event");
        return;
    };
    let Ok(mut clients) = subscribers.lock() else {
        eprintln!("nyxd: subscriber lock poisoned");
        return;
    };
    clients.retain(|client| match client.try_send(serialized.clone()) {
        Ok(()) | Err(TrySendError::Full(_)) => true,
        Err(TrySendError::Disconnected(_)) => false,
    });
}

fn serve_client(mut stream: UnixStream, subscribers: &Subscribers) {
    let (sender, receiver) = mpsc::sync_channel::<String>(64);
    if let Ok(mut clients) = subscribers.lock() {
        clients.push(sender);
    } else {
        return;
    }
    thread::spawn(move || {
        while let Ok(event) = receiver.recv() {
            if writeln!(stream, "{event}").and_then(|_| stream.flush()).is_err() {
                break;
            }
        }
    });
}

fn socket_path() -> String {
    env::var("NYXD_SOCKET_PATH").unwrap_or_else(|_| DEFAULT_SOCKET.to_owned())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = socket_path();
    if let Ok(metadata) = fs::symlink_metadata(&path) {
        if !metadata.file_type().is_socket() {
            return Err(format!("refusing to replace non-socket path {path}").into());
        }
        fs::remove_file(&path)?;
    }
    let listener = UnixListener::bind(&path)?;
    fs::set_permissions(&path, fs::Permissions::from_mode(0o660))?;
    let subscribers: Subscribers = Arc::new(Mutex::new(Vec::new()));
    let client_subscribers = Arc::clone(&subscribers);
    thread::spawn(move || {
        for incoming in listener.incoming() {
            match incoming {
                Ok(stream) => serve_client(stream, &client_subscribers),
                Err(error) => eprintln!("nyxd: socket accept failed: {error}"),
            }
        }
    });

    let mut journal = Command::new("journalctl")
        .args(["--follow", "--output=json", "--priority=err..emerg"])
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()?;
    let stdout = journal.stdout.take().ok_or("journalctl stdout unavailable")?;
    for line in BufReader::new(stdout).lines() {
        match line {
            Ok(line) => {
                if let Some(event) = event_from_journal(&line) {
                    publish(&subscribers, &event);
                }
            }
            Err(error) => eprintln!("nyxd: journal read failed: {error}"),
        }
    }
    let status = journal.wait()?;
    Err(format!("journalctl exited with {status}").into())
}
