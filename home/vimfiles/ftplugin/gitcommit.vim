autocmd BufEnter <buffer> silent wincmd L
autocmd BufEnter <buffer> silent if has('win32') | e ++ff=dos | endif
