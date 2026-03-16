#!/bin/bash
# Bash completion for warden

_warden_completions() {
    local cur prev words cword
    _init_completion || return

    local commands="id pkg backup restore mole update"
    local id_commands="switch list show"
    local pkg_commands="scan apply install"
    local mole_commands="clean optimize analyze status"

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
            if [[ "${prev}" == "-m" ]]; then
                COMPREPLY=($(compgen -W "all git ssh pkg git,ssh git,pkg ssh,pkg git,ssh,pkg" -- "${cur}"))
            elif [[ "${prev}" == "-o" || "${prev}" == "--output" ]]; then
                _filedir
            else
                COMPREPLY=($(compgen -W "-m -o --output --include-missing --skip-scan --help" -- "${cur}"))
            fi
            return
            ;;
        restore)
            if [[ "${prev}" == "-m" ]]; then
                COMPREPLY=($(compgen -W "all git ssh pkg git,ssh git,pkg ssh,pkg git,ssh,pkg" -- "${cur}"))
            else
                _filedir 'tar.gz'
                COMPREPLY+=($(compgen -W "-m --help" -- "${cur}"))
            fi
            return
            ;;
        mole)
            local sub2=""
            for ((i = subcmd_pos + 1; i < cword; i++)); do
                case "${words[i]}" in
                    clean | optimize | analyze | status)
                        sub2="${words[i]}"
                        break
                        ;;
                esac
            done
            if [[ -z "${sub2}" ]]; then
                COMPREPLY=($(compgen -W "${mole_commands} --help" -- "${cur}"))
            else
                case "${sub2}" in
                    analyze)
                        _filedir -d
                        ;;
                    status)
                        COMPREPLY=($(compgen -W "--json --help" -- "${cur}"))
                        ;;
                    *)
                        COMPREPLY=($(compgen -W "--help" -- "${cur}"))
                        ;;
                esac
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
