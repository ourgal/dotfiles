nmap <buffer> <CR> <C-]>
nmap <buffer> <BS> <C-T>
nnoremap <buffer> o silent! /'[a-z]\{2,\}'<CR>
nnoremap <buffer> q <cmd>q<cr>

autocmd BufEnter <buffer> silent wincmd T
