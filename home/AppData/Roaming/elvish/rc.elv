# Aliases (powershell/clink style)
fn ls {|@a| exa $@a }
fn ll {|@a| exa -l $@a }
fn la {|@a| exa -a $@a }
fn l {|@a| exa -la $@a }
fn cat {|@a| bat $@a }
fn grep {|@a| rg $@a }
fn find {|@a| fd $@a }
fn cd {|@a| z $@a }
fn mv {|@a| (external mv) -i $@a }
fn cp {|@a| (external cp) -i $@a }
fn rm {|@a| (external rm) -i $@a }
fn top {|@a| btop $@a }
fn g {|@a| git $@a }
fn lg {|@a| lazygit $@a }
fn reboot {|@a| shutdown /r /t 0 $@a }
fn poweroff {|@a| shutdown /s /t 0 $@a }

set edit:insert:binding['('] = { edit:insert-at-dot '()' ; edit:move-dot-left }
set edit:insert:binding['['] = { edit:insert-at-dot '[]' ; edit:move-dot-left }
set edit:insert:binding['{'] = { edit:insert-at-dot '{}' ; edit:move-dot-left }
set edit:insert:binding['"'] = { edit:insert-at-dot '""' ; edit:move-dot-left }
set edit:insert:binding["'"] = { edit:insert-at-dot "''" ; edit:move-dot-left }
