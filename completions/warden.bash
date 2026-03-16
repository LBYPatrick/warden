#!/bin/bash
# Bash completion for warden

_warden_completions() {
    local cur prev words cword
    _init_completion || return

    local commands="switch list show scan apply update backup restore"
    local backup_commands="git ssh all"
    local restore_commands="git ssh all"

    case "${cword}" in
        1)
            COMPREPLY=($(compgen -W "${commands} --help -h -c --dry-run" -- "${cur}"))
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
        switch | show)
            # Try to get targets from warden list (parse output)
            local targets
            targets=$(warden list 2>/dev/null | grep -oP '(?<=◉ )\S+' | sed 's/\x1b\[[0-9;]*m//g')
            if [[ -n "${targets}" ]]; then
                COMPREPLY=($(compgen -W "${targets}" -- "${cur}"))
            fi
            return
            ;;
        backup)
            # Determine sub-subcommand
            local sub2=""
            for ((i = subcmd_pos + 1; i < cword; i++)); do
                case "${words[i]}" in
                    git | ssh)
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
                    git | ssh)
                        sub2="${words[i]}"
                        break
                        ;;
                esac
            done
            if [[ -z "${sub2}" ]]; then
                COMPREPLY=($(compgen -W "${restore_commands} --help" -- "${cur}"))
            else
                # Complete file paths for the archive argument
                _filedir 'tar.gz'
                COMPREPLY+=($(compgen -W "--help" -- "${cur}"))
            fi
            return
            ;;
        list | scan | update)
            COMPREPLY=($(compgen -W "--help" -- "${cur}"))
            return
            ;;
        apply)
            COMPREPLY=($(compgen -W "-f --force --help" -- "${cur}"))
            return
            ;;
    esac

    # Default: top-level commands
    COMPREPLY=($(compgen -W "${commands} --help -h -c --dry-run" -- "${cur}"))
}

complete -F _warden_completions warden
