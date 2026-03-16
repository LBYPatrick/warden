#compdef warden

# Zsh completion for warden

_warden_targets() {
    local targets
    targets=(${(f)"$(warden id list 2>/dev/null | grep -oP '(?<=◉ )\S+' | sed 's/\x1b\[[0-9;]*m//g')"})
    if [[ ${#targets} -gt 0 ]]; then
        _describe 'target' targets
    fi
}

_warden() {
    local -a commands
    commands=(
        'id:git identity management'
        'pkg:system package management'
        'backup:backup identities, SSH config, or both'
        'restore:restore from backup archive'
        'update:self-update warden from git'
    )

    _arguments -C \
        '-c[config file override]:config file:_files' \
        '--dry-run[preview without making changes]' \
        '--no-color[disable colored output]' \
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
                id)
                    local -a id_commands
                    id_commands=(
                        'switch:apply a git identity'
                        'list:list available targets'
                        'show:show current or specific target config'
                    )
                    _arguments -C \
                        '1:id command:->id_cmd' \
                        '*::arg:->id_args'
                    case "$state" in
                        id_cmd)
                            _describe 'id command' id_commands
                            ;;
                        id_args)
                            case "${words[1]}" in
                                switch)
                                    _arguments '1:target:_warden_targets'
                                    ;;
                                show)
                                    _arguments '1::target:_warden_targets'
                                    ;;
                                list)
                                    _arguments '--help[show help]'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
                pkg)
                    local -a pkg_commands
                    pkg_commands=(
                        'scan:scan system and update config'
                        'apply:install packages from config'
                        'install:install packages via any manager'
                    )
                    _arguments -C \
                        '1:pkg command:->pkg_cmd' \
                        '*::arg:->pkg_args'
                    case "$state" in
                        pkg_cmd)
                            _describe 'pkg command' pkg_commands
                            ;;
                        pkg_args)
                            case "${words[1]}" in
                                scan)
                                    _arguments '--help[show help]'
                                    ;;
                                apply)
                                    _arguments \
                                        '(-f --force)'{-f,--force}'[reinstall all]' \
                                        '--help[show help]'
                                    ;;
                                install)
                                    _arguments \
                                        '--save[add to warden.jsonc]' \
                                        '--any[bypass OS check]' \
                                        '--help[show help]' \
                                        '*:package (manager\:pkg):'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
                backup)
                    local -a backup_commands
                    backup_commands=(
                        'git:backup identities and signing keys'
                        'ssh:backup SSH config and identity keys'
                        'all:backup everything'
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
                                        '(-o --output)'{-o,--output}'[output path]:file:_files' \
                                        '--help[show help]'
                                    ;;
                                ssh)
                                    _arguments \
                                        '(-o --output)'{-o,--output}'[output path]:file:_files' \
                                        '--include-missing[include hosts with missing keys]' \
                                        '--help[show help]'
                                    ;;
                                all)
                                    _arguments \
                                        '(-o --output)'{-o,--output}'[output path]:file:_files' \
                                        '--include-missing[include hosts with missing keys]' \
                                        '(-s --scan)'{-s,--scan}'[re-scan packages before backup]' \
                                        '--help[show help]'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
                restore)
                    local -a restore_commands
                    restore_commands=(
                        'git:restore git identities'
                        'ssh:restore SSH config'
                        'all:restore everything'
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
                update)
                    _arguments \
                        '1::branch:' \
                        '--help[show help]'
                    ;;
            esac
            ;;
    esac
}

_warden "$@"
