# NyxOS glue for Nushell. build.sh installs this as
# /usr/local/share/nushell/vendor/autoload/nyx.nu so every interactive shell loads it.

$env.config.show_banner = false

# `ask list the biggest files` is the same as `nyx "list the biggest files"`.
def ask [...words: string] {
    ^nyx ...$words
}

# Show alerts that nyxd logged since the last prompt. Only runs once the first alert exists.
$env.config.hooks.pre_prompt = ($env.config.hooks.pre_prompt | append {||
    if ("/run/nyx/alerts.jsonl" | path exists) { ^nyx notify }
})

if $nu.is-interactive {
    print $"(ansi green_bold)NyxOS(ansi reset): AI-first shell. Describe what you want, it proposes the command, you confirm."
    print "  ask list the biggest files   |   ask install htop   |   nyx alerts   |   nyx config"
}
