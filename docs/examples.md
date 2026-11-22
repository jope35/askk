# Example requests

One hundred natural-language requests and the one-line Bash command the agent should return.

Grounded in `docs/agent-spec.md` and `.opencode/agents/bash.md`. Devin Desktop Terminal Command is the UX analog: natural language in the terminal (`Cmd`/`Ctrl+I`) yields CLI syntax, then the user reviews before run ([Command overview](https://docs.devin.ai/desktop/command/windsurf-overview), [Terminal](https://docs.devin.ai/desktop/terminal.md)). Categories follow public NL-to-shell tools (Copilot CLI `suggest`, Warp AI Command Search): files, find, git, docker, processes, jq/text, systemd, curl, tar/rsync, failed-command repair, and refuse-or-clarify.

Format matches the agent prompt: Input, then Output. Each output is one syntactically complete Bash line: no fences, no preamble, no here-document.

## Files and directories

Input: List all files in this folder
Output: ls -la

Input: List hidden entries in this folder, not `.` or `..`
Output: find . -maxdepth 1 -name '.*' ! -name '.' ! -name '..'

Input: Make a directory named tmp/cache, including parents
Output: mkdir -p -- tmp/cache

Input: Create an empty file called notes.txt
Output: touch -- notes.txt

Input: Show disk usage of this directory, human readable, one level
Output: du -h --max-depth=1 .

Input: Print the ten largest files in this directory
Output: find . -maxdepth 1 -type f -printf '%s\t%p\n' | sort -nr | head -n 10

Input: Count regular files in this folder, not recursive
Output: find . -maxdepth 1 -type f -printf '.' | wc -c

Input: Goal: list contents of /var/log/nginx. Failed command: ls /var/log/nginx. Error: Permission denied
Output: namei -l /var/log/nginx; id

Input: Print permissions of /etc/passwd in numeric form
Output: stat -c '%a %n' -- /etc/passwd

Input: Follow the symlink at ./current and print the real path
Output: realpath -- ./current

## Find

Input: Pick up all PNG files here
Output: find . -maxdepth 1 -type f -name '*.png'

Input: Recursively find all Python files
Output: find . -type f -name '*.py'

Input: Find Python files larger than 1MB
Output: find . -type f -name '*.py' -size +1M

Input: Find all files larger than 100MB in my home directory
Output: find "$HOME" -type f -size +100M

Input: List all files modified in the last 7 days
Output: find . -type f -mtime -7

Input: Find files named exactly Makefile
Output: find . -type f -name Makefile

Input: Find empty files under ./src
Output: find ./src -type f -empty

Input: Find directories named node_modules at any depth
Output: find . -type d -name node_modules

Input: Find .log files under /var/log modified more than 30 days ago
Output: find /var/log -type f -name '*.log' -mtime +30

Input: List all .log files in /var/log modified in the last 24 hours, sorted by size
Output: find /var/log -type f -name '*.log' -mtime -1 -printf '%s\t%p\n' | sort -nr

Input: Find files with the user executable bit set under ./bin
Output: find ./bin -type f -perm -u+x

Input: Find files owned by root in ./data
Output: find ./data -user root

## Copy, move, rename

Input: Rename each folder that starts with `old-`
Output: for d in old-*/; do mv -- "$d" "new-${d#old-}"; done

Input: Rename file draft.txt to final.txt
Output: mv -- draft.txt final.txt

Input: Copy config.yaml to config.yaml.bak
Output: cp -- config.yaml config.yaml.bak

Input: Copy all .jpg files from ./incoming to ./photos
Output: find ./incoming -maxdepth 1 -type f -name '*.jpg' -exec cp -t ./photos -- {} +

Input: Move every .tmp file in this folder into ./trash
Output: find . -maxdepth 1 -type f -name '*.tmp' -exec mv -t ./trash -- {} +

Input: Create a symlink named ./app pointing at ./releases/current
Output: ln -s -- ./releases/current ./app

Input: Recursively copy ./src to ./src-backup, preserving timestamps and permissions
Output: cp -a -- ./src ./src-backup

Input: Change into ~/projects/askk
Output: cd -- "$HOME/projects/askk"

## Text and JSON

Input: Read the `name` of each item in `data.json` with `jq`
Output: jq -r '.items[].name' data.json

Input: Pretty-print data.json with jq
Output: jq . data.json

Input: Extract the version field from package.json with jq
Output: jq -r '.version' package.json

Input: Show the last 20 lines of app.log
Output: tail -n 20 -- app.log

Input: Follow nginx error log as it grows
Output: tail -F -- /var/log/nginx/error.log

Input: Show the first 10 lines of README.md
Output: head -n 10 -- README.md

Input: Count lines in access.log
Output: wc -l -- access.log

Input: Search for TODO in ./src recursively
Output: grep -R -- 'TODO' ./src

Input: Goal: recursively find the literal text error[42] in ./logs. Failed command: grep -R error[42] ./logs. Error: grep: Unmatched [ or [^
Output: grep -R -F -- 'error[42]' ./logs

Input: Replace foo with bar in place in config.txt and keep a backup
Output: sed -i.bak 's/foo/bar/g' -- config.txt

Input: Print the second column of data.csv, comma separated
Output: cut -d, -f2 -- data.csv

Input: Sort unique lines in names.txt
Output: sort -u -- names.txt

Input: Diff a.txt and b.txt, unified
Output: diff -u -- a.txt b.txt

Input: Search for redraw in this directory, print the first and third space-separated columns, then sort
Output: grep -F -- 'redraw' ./* | awk '{print $1, $3}' | sort

Input: Convert all text in names.txt to lowercase
Output: tr '[:upper:]' '[:lower:]' < names.txt

Input: Show which lines in left.txt are not in right.txt
Output: comm -23 <(sort -- left.txt) <(sort -- right.txt)

## Git

Input: Show git status
Output: git status

Input: Show a compact graph of the last 10 commits across all branches
Output: git log --oneline --graph --decorate --all -n 10

Input: Show git log for last week with author names
Output: git log --since='1 week ago' --pretty=format:'%h %an %s'

Input: Undo the most recent local commit but keep the changes staged
Output: git reset --soft HEAD~1

Input: List local branches
Output: git branch

Input: Create and switch to branch feature/login
Output: git checkout -b feature/login

Input: Stash uncommitted changes
Output: git stash push

Input: Reapply the latest stash and keep it in the stash list
Output: git stash apply

Input: Remove all .DS_Store files from git tracking without deleting them from disk
Output: git ls-files -z -- '.DS_Store' '**/.DS_Store' | xargs -0 -r git rm --cached --

Input: List git branches sorted by last commit
Output: git for-each-ref --sort=-committerdate --format='%(refname:short) %(committerdate:relative)' refs/heads

Input: Show unstaged changes
Output: git diff

Input: Stage all changes
Output: git add -A

Input: Commit staged changes with message fix parser
Output: git commit -m 'fix parser'

Input: Initialize a new git repository
Output: git init

Input: Show who last touched each line of src/main.c
Output: git blame -- src/main.c

Input: Show remote URLs
Output: git remote -v

## Docker

Input: List all running Docker containers
Output: docker ps

Input: List all Docker containers including stopped ones
Output: docker ps -a

Input: Show docker container resource usage
Output: docker stats

Input: Open an interactive shell in the running container named api
Output: docker exec -it api /bin/bash

Input: Copy /var/log/app.log from container api to ./app.log
Output: docker cp api:/var/log/app.log ./app.log

Input: Follow logs for container api
Output: docker logs -f api

Input: Show Docker disk usage and reclaimable space
Output: docker system df -v

Input: Build an image tagged app:dev from this directory
Output: docker build -t app:dev .

## Processes

Input: Find processes using the most memory
Output: ps aux --sort=-%mem | head -n 11

Input: List processes named nginx
Output: pgrep -a -x nginx

Input: Kill processes named node with SIGTERM
Output: pkill -TERM -x node

Input: Show what is listening on port 8080
Output: ss -ltnp 'sport = :8080'

Input: Show which process has file ./lock held open
Output: lsof -- ./lock

Input: Print my user id and groups
Output: id

Input: Show free memory
Output: free -h

## System and services

Input: Show the last 50 journal entries for ssh.service without opening a pager
Output: journalctl -u ssh.service -n 50 --no-pager

Input: Show status of nginx.service without a pager
Output: systemctl status nginx.service --no-pager

Input: Restart nginx.service
Output: sudo systemctl restart nginx.service

Input: List failed systemd units
Output: systemctl --failed --no-pager

Input: Print OS identification
Output: cat /etc/os-release

Input: Recursively chmod 777 on /
Output: ! printf 'Cannot generate a safe command: %s\n' 'Refusing recursive chmod on /' >&2

Input: Show today's date in ISO format
Output: date -Iseconds

## Network and transfer

Input: Test whether github.com answers on HTTPS
Output: curl -I --fail --location -- https://github.com/

Input: Look up DNS A records for example.com
Output: dig +short A example.com

Input: Show my IPv4 addresses
Output: ip -4 -br addr

Input: Download https://example.com/file.tar.gz into ./file.tar.gz
Output: curl --fail --location -o file.tar.gz -- https://example.com/file.tar.gz

Input: Copy ./release.tgz to user@host:tmp/ with scp
Output: scp ./release.tgz user@host:tmp/

Input: Show established TCP connections
Output: ss -t state established

## Archives and sync

Input: Recursively gzip regular files under /var/log whose names end in .log and which were modified at least 31×24 hours ago
Output: find /var/log -type f -name '*.log' -mtime +30 -exec gzip -- {} +

Input: Create a tar.gz of ./src named src.tar.gz
Output: tar -czf src.tar.gz -- src

Input: Extract archive backup.tar.gz into a new empty directory ./restore
Output: mkdir -p -- ./restore && tar -xzf backup.tar.gz -C ./restore

Input: Dry-run rsync of ./data/ to /backup/data/, itemize changes, do not delete extras
Output: rsync -a --dry-run --itemize-changes -- ./data/ /backup/data/

## Safety, recovery, and uncertainty

Input: Delete empty directories below ./build, including parents that become empty during traversal, but not ./build itself
Output: find ./build -mindepth 1 -type d -empty -delete

Input: Install htop. No distro or package manager is provided.
Output: if [ -e /etc/os-release ]; then cat /etc/os-release; else cat /usr/lib/os-release; fi; command -v apt-get dnf yum zypper pacman apk

Input: Delete the file named --help in this folder
Output: rm -- --help

Input: Delete the old backup
Output: ! printf 'Clarify: %s\n' 'Which path should be deleted?' >&2

Input: How does find -mtime work?
Output: man find

Input: Wipe the disk
Output: ! printf 'Cannot generate a safe command: %s\n' 'No explicit block device or filesystem target' >&2
