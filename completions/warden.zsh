#compdef warden

# Zsh completion for warden

_warden_targets() {
    local targets
    targets=(${(f)"$(warden list 2>/dev/null | grep -oP '(?<=◉ )\S+' | sed 's/\x1b\[[0-9;]*m//g')"})
    if [[ ${#targets} -gt 0 ]]; then
        _describe 'target' targets
    fi
}

_warden() {
    local -a commands
    commands=(
        'switch:apply a git identity'
        'list:list available targets'
        'show:show current or specific target config'
        'scan:scan system and update packages/tools in config'
        'apply:install packages/tools from config onto the system'
        'install:install packages via any package manager'
        'update:self-update warden from git'
        'backup:backup git identities or SSH config'
        'restore:restore git identities or SSH config from backup'
    )

    _arguments -C \
        '-c[path to warden.jsonc config file]:config file:_files' \
        '--dry-run[show what would be done without making changes]' \
        '-h[show help]' \
        '--help[show help]' \
        '1:command:->command' \
        '*::arg:->args'

    case "$state" in
        command)
            _describe 'command' commands
            ;;
        args)
            case "${words[1]}" in
                switch)
                    _arguments '1:target:_warden_targets'
                    ;;
                show)
                    _arguments '1::target:_warden_targets'
                    ;;
                list | scan | update)
                    _arguments '--help[show help]'
                    ;;
                apply)
                    _arguments \
                        '(-f --force)'{-f,--force}'[reinstall all packages even if already present]' \
                        '--help[show help]'
                    ;;
                install)
                    _arguments \
                        '--save[add installed packages to warden.jsonc]' \
                        '--any[bypass OS platform check]' \
                        '--help[show help]' \
                        '*:package (manager\:pkg):'
                    ;;
                backup)
                    local -a backup_commands
                    backup_commands=(
                        'git:backup warden.jsonc and signing keys'
                        'ssh:backup SSH config and identity keys'
                        'all:backup both git identities and SSH config'
                    )
                    _arguments -C \
                        '1:backup type:->backup_type' \
                        '*::arg:->backup_args'
                    case "$state" in
                        backup_type)
                            _describe 'backup type' backup_commands
                            ;;
                        backup_args)
                            case "${words[1]}" in
                                git)
                                    _arguments \
                                        '(-o --output)'{-o,--output}'[output archive path]:file:_files' \
                                        '--help[show help]'
                                    ;;
                                ssh)
                                    _arguments \
                                        '(-o --output)'{-o,--output}'[output archive path]:file:_files' \
                                        '--include-missing[include hosts with missing keys]' \
                                        '--help[show help]'
                                    ;;
                                all)
                                    _arguments \
                                        '(-o --output)'{-o,--output}'[output archive path]:file:_files' \
                                        '--include-missing[include SSH hosts with missing keys]' \
                                        '(-s --scan)'{-s,--scan}'[re-scan system packages before backup]' \
                                        '--help[show help]'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
                restore)
                    local -a restore_commands
                    restore_commands=(
                        'git:restore git identities from backup'
                        'ssh:restore SSH config from backup'
                        'all:restore both git and SSH from backup'
                    )
                    _arguments -C \
                        '1:restore type:->restore_type' \
                        '*::arg:->restore_args'
                    case "$state" in
                        restore_type)
                            _describe 'restore type' restore_commands
                            ;;
                        restore_args)
                            _arguments \
                                '1:archive:_files -g "*.tar.gz"' \
                                '--help[show help]'
                            ;;
                    esac
                    ;;
            esac
            ;;
    esac
}

_warden "$@"
