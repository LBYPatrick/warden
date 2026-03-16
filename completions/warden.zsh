#compdef warden

# Zsh completion for warden

_warden_targets() {
    local targets
    targets=(${(f)"$(warden id list 2>/dev/null | grep -oP '(?<=◉ )\S+' | sed 's/\x1b\[[0-9;]*m//g')"})
    if [[ ${#targets} -gt 0 ]]; then
        _describe 'target' targets
    fi
}

_warden_modules() {
    local -a modules
    modules=(
        'all:all modules'
        'git:identities and signing keys'
        'ssh:SSH config and identity keys'
        'pkg:packages and tools'
        'git,ssh:identities and SSH'
        'git,pkg:identities and packages'
        'ssh,pkg:SSH and packages'
        'git,ssh,pkg:all modules'
    )
    _describe 'modules' modules
}

_warden() {
    local -a commands
    commands=(
        'id:git identity management'
        'pkg:system package management'
        'backup:backup modules (default: all)'
        'restore:restore modules from backup archive'
        'mole:system cleanup and optimization (macOS)'
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
                    _arguments \
                        '-m[modules to backup]:modules:_warden_modules' \
                        '(-o --output)'{-o,--output}'[output path]:file:_files' \
                        '--include-missing[include hosts with missing keys]' \
                        '--skip-scan[skip re-scanning packages]' \
                        '--help[show help]'
                    ;;
                restore)
                    _arguments \
                        '-m[modules to restore]:modules:_warden_modules' \
                        '1:archive:_files -g "*.tar.gz"' \
                        '--help[show help]'
                    ;;
                mole)
                    local -a mole_commands
                    mole_commands=(
                        'clean:deep system cleanup'
                        'optimize:rebuild system databases'
                        'analyze:visual disk space explorer'
                        'status:system health dashboard'
                    )
                    _arguments -C \
                        '1:mole command:->mole_cmd' \
                        '*::arg:->mole_args'
                    case "$state" in
                        mole_cmd)
                            _describe 'mole command' mole_commands
                            ;;
                        mole_args)
                            case "${words[1]}" in
                                analyze)
                                    _arguments '1::path:_directories'
                                    ;;
                                status)
                                    _arguments '--json[JSON output]' '--help[show help]'
                                    ;;
                                *)
                                    _arguments '--help[show help]'
                                    ;;
                            esac
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
