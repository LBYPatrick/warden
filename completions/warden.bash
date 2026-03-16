#!/bin/bash
# Bash completion for warden

_warden_completions() {
    local cur prev words cword
    _init_completion || return

    local commands="id pkg backup restore update"
    local id_commands="switch list show"
    local pkg_commands="scan apply install"
    local backup_commands="git ssh all"
    local restore_commands="git ssh all"

    case "${cword}" in
        1)
            COMPREPLY=($(compgen -W "${commands} --help -h -c --dry-run --no-color" -- "${cur}"))
            return
            ;;
    esac

    # Handle -c flag (next arg is a file path)
    if [[ "${prev}" == "-c" ]]; then
        _filedir
        return
    fi

    # Find the subcommand position (skip global flags)
    local subcmd=""
    local subcmd_pos=0
    local i
    for ((i = 1; i < cword; i++)); do
        case "${words[i]}" in
            -c) ((i++)) ;; # skip -c and its argument
            -*)  ;;
            *)
                if [[ -z "${subcmd}" ]]; then
                    subcmd="${words[i]}"
                    subcmd_pos=$i
                fi
                break
                ;;
        esac
    done

    case "${subcmd}" in
        id)
            # Determine sub-subcommand
            local sub2=""
            for ((i = subcmd_pos + 1; i < cword; i++)); do
                case "${words[i]}" in
                    switch | list | show)
                        sub2="${words[i]}"
                        break
                        ;;
                esac
            done
            if [[ -z "${sub2}" ]]; then
                COMPREPLY=($(compgen -W "${id_commands} --help" -- "${cur}"))
            else
                case "${sub2}" in
                    switch | show)
                        # Try to get targets from warden id list
                        local targets
                        targets=$(warden id list 2>/dev/null | grep -oP '(?<=◉ )\S+' | sed 's/\x1b\[[0-9;]*m//g')
                        if [[ -n "${targets}" ]]; then
                            COMPREPLY=($(compgen -W "${targets}" -- "${cur}"))
                        fi
                        ;;
                    list)
                        COMPREPLY=($(compgen -W "--help" -- "${cur}"))
                        ;;
                esac
            fi
            return
            ;;
        pkg)
            local sub2=""
            for ((i = subcmd_pos + 1; i < cword; i++)); do
                case "${words[i]}" in
                    scan | apply | install)
                        sub2="${words[i]}"
                        break
                        ;;
                esac
            done
            if [[ -z "${sub2}" ]]; then
                COMPREPLY=($(compgen -W "${pkg_commands} --help" -- "${cur}"))
            else
                case "${sub2}" in
                    scan)
                        COMPREPLY=($(compgen -W "--help" -- "${cur}"))
                        ;;
                    apply)
                        COMPREPLY=($(compgen -W "-f --force --help" -- "${cur}"))
                        ;;
                    install)
                        COMPREPLY=($(compgen -W "--save --any --help" -- "${cur}"))
                        ;;
                esac
            fi
            return
            ;;
        backup)
            local sub2=""
            for ((i = subcmd_pos + 1; i < cword; i++)); do
                case "${words[i]}" in
                    git | ssh | all)
                        sub2="${words[i]}"
                        break
                        ;;
                esac
            done
            if [[ -z "${sub2}" ]]; then
                COMPREPLY=($(compgen -W "${backup_commands} --help" -- "${cur}"))
            else
                case "${sub2}" in
                    git)
                        COMPREPLY=($(compgen -W "-o --output --help" -- "${cur}"))
                        [[ "${prev}" == "-o" || "${prev}" == "--output" ]] && _filedir
                        ;;
                    ssh)
                        COMPREPLY=($(compgen -W "-o --output --include-missing --help" -- "${cur}"))
                        [[ "${prev}" == "-o" || "${prev}" == "--output" ]] && _filedir
                        ;;
                    all)
                        COMPREPLY=($(compgen -W "-o --output --include-missing -s --scan --help" -- "${cur}"))
                        [[ "${prev}" == "-o" || "${prev}" == "--output" ]] && _filedir
                        ;;
                esac
            fi
            return
            ;;
        restore)
            local sub2=""
            for ((i = subcmd_pos + 1; i < cword; i++)); do
                case "${words[i]}" in
                    git | ssh | all)
                        sub2="${words[i]}"
                        break
                        ;;
                esac
            done
            if [[ -z "${sub2}" ]]; then
                COMPREPLY=($(compgen -W "${restore_commands} --help" -- "${cur}"))
            else
                _filedir 'tar.gz'
                COMPREPLY+=($(compgen -W "--help" -- "${cur}"))
            fi
            return
            ;;
        update)
            COMPREPLY=($(compgen -W "--help" -- "${cur}"))
            return
            ;;
    esac

    # Default: top-level commands
    COMPREPLY=($(compgen -W "${commands} --help -h -c --dry-run --no-color" -- "${cur}"))
}

complete -F _warden_completions warden
