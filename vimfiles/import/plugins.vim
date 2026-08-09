let gh_proxy = 'https://jiashu.1win.eu.org/https://github.com/'
"{{{ plugins
call plug#begin()
"{{{ align
" Plug 'godlygeek/tabular'
" Plug 'junegunn/vim-easy-align', { 'on': [ '<Plug>(EasyAlign)', 'EasyAlign' ] }
" Plug 'vim-scripts/align', { 'on': 'Align' }
"}}}
"{{{ auto pair
" Plug 'tmsvg/pear-tree'
" Plug 'cohama/lexima.vim'
" Plug 'Raimondi/delimitMate'
"}}}
"{{{ pair
Plug gh_proxy . 'tpope/vim-endwise'
"}}}
"{{{ termux
if g:is_android
  Plug gh_proxy . 'vim-utilities/termux-clipboard'
endif
"}}}
"{{{ command preview
Plug 'https://gitcode.com/gh_mirrors/tr/traces.vim'
"}}}
"{{{ comment
" Plug gh_proxy . 'tyru/caw.vim'
"}}}
"{{{ dot repeat
Plug gh_proxy . 'tpope/vim-repeat'
"}}}
"{{{ file support
Plug gh_proxy . 'tpope/vim-eunuch' " file command
" Plug 'pbrisbin/vim-mkdir' " auto create dir
" Plug 'lambdalisue/vim-suda' " auto sudo when write
"}}}
"{{{ file manager
" Plug 'habamax/vim-dir'
" Plug 'nda-cunh/SupraWater'
" Plug 'Ashik80/VimExplorer'
" Plug 'tpope/vim-vinegar'

Plug 'https://gitcode.com/gh_mirrors/vi/vim-dirvish'
Plug gh_proxy . 'roginfarrer/vim-dirvish-dovish'
"}}}
"{{{ format
Plug 'https://gitcode.com/gh_mirrors/ne/neoformat'
"}}}
"{{{ file picker
Plug 'https://gitcode.com/gh_mirrors/fz/fzf.vim'
"}}}
"{{{ git
if executable('git')
  Plug gh_proxy . 'tpope/vim-fugitive'
  Plug 'https://gitcode.com/gh_mirrors/vi/vim-gitgutter'
endif
Plug gh_proxy . 'rhysd/conflict-marker.vim'
Plug gh_proxy . 'Eliot00/git-lens.vim'
" Plug 'rhysd/git-messenger.vim'
"}}}
"{{{ integration
Plug gh_proxy . 'alker0/chezmoi.vim' " chezmoi

" Plug 'raghur/vim-ghost' " browser text input
" Plug 'roxma/nvim-yarp', v:version >= 800 && !has('nvim') ? {} : { 'on': [], 'for': [] }
" Plug 'roxma/vim-hug-neovim-rpc', v:version >= 800 && !has('nvim') ? {} : { 'on': [], 'for': [] }
"
Plug gh_proxy . 'tpope/vim-dispatch' " async make
Plug 'https://gitcode.com/gh_mirrors/vi/vim-floaterm' " terminal
"}}}
"{{{ enhance
Plug gh_proxy . 'tpope/vim-unimpaired'
Plug gh_proxy . 'nelstrom/vim-visual-star-search'
Plug gh_proxy . 'zef/vim-cycle' " C-A C-X
Plug 'https://gitcode.com/gh_mirrors/vi/vim-exchange' " cx exchange text
Plug gh_proxy . 'haya14busa/is.vim' " auto nohlsearch
Plug 'https://gitcode.com/gh_mirrors/vi/vim-matchup' " enhance asterrisk
Plug gh_proxy . 'svermeulen/vim-subversive' " substitute motion
Plug 'https://gitcode.com/gh_mirrors/sw/switch.vim' " regex replace motion
Plug 'https://gitcode.com/gh_mirrors/sp/splitjoin.vim' " gS gJ list split and join
Plug 'https://gitcode.com/gh_mirrors/ta/targets.vim' " enhance targets
Plug 'https://gitcode.com/gh_mirrors/vi/vim-expand-region' " + expand region
Plug 'https://gitcode.com/gh_mirrors/vi/vim-visual-multi' " multiple cursor
Plug gh_proxy . 'tpope/vim-surround' " pair markers
" Plug 'vim-polyglot/vim-polyglot' " syntax highlight, conflicts with auto session
Plug 'https://gitcode.com/gh_mirrors/vi/vim-which-key' " menu
Plug 'https://gitcode.com/gh_mirrors/vi/vimcdoc' " vim chinese doc
Plug 'https://gitcode.com/gh_mirrors/vi/vim-qf' " quickfix
"}}}
"{{{ lisp
if executable('cargo') && !g:is_android
  Plug 'https://gitcode.com/gh_mirrors/pa/parinfer-rust', {'do': 'cargo build --release'}
endif
"}}}
"{{{ markdown
Plug 'https://gitcode.com/gh_mirrors/ta/tabular'
Plug gh_proxy . 'preservim/vim-markdown'
"}}}
"{{{ latex
Plug 'https://gitcode.com/gh_mirrors/vi/vimtex', { 'for': 'tex' }
"}}}
"{{{ lsp
if executable('node')
  Plug 'https://gitcode.com/gh_mirrors/co/coc.nvim', {'branch': 'release'}
endif
" Plug 'yegappan/lsp'
"}}}
"{{{ lint
" Plug 'dense-analysis/ale'
"}}}
"{{{ org
Plug 'https://gitcode.com/gh_mirrors/vi/vim-orgmode'
Plug gh_proxy . 'tpope/vim-speeddating'
"}}}
"{{{ snippet
Plug 'https://gitcode.com/gh_mirrors/vi/vim-snippets'
" Plug 'SirVer/ultisnips'
"}}}
"{{{ template
Plug gh_proxy . 'aperezdc/vim-template'
"}}}
"{{{ session
Plug gh_proxy . 'ourgal/vim-workspace'
"}}}
"{{{ status line
Plug 'https://gitcode.com/gh_mirrors/li/lightline.vim'
"}}}
"{{{ theme
" Plug 'ghifarit53/tokyonight-vim'
" Plug 'https://codeberg.org/mao-yining/vim-catppuccin'
Plug 'https://gitcode.com/gh_mirrors/vim17/vim', { 'as': 'embark', 'branch': 'main' }
" Plug 'https://gitcode.com/gh_mirrors/on/onedark.vim'
"}}}
call plug#end()
"}}}
