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
Plug 'tpope/vim-endwise'
"}}}
"{{{ termux
if g:is_android
    Plug 'vim-utilities/termux-clipboard'
endif
"}}}
"{{{ command preview
Plug 'markonm/traces.vim'
"}}}
"{{{ comment
Plug 'tyru/caw.vim'
"}}}
"{{{ dot repeat
Plug 'tpope/vim-repeat'
"}}}
"{{{ file support
Plug 'tpope/vim-eunuch' " file command
" Plug 'pbrisbin/vim-mkdir' " auto create dir
" Plug 'lambdalisue/vim-suda' " auto sudo when write
"}}}
"{{{ file manager
" Plug 'habamax/vim-dir'
" Plug 'nda-cunh/SupraWater'
" Plug 'Ashik80/VimExplorer'
" Plug 'tpope/vim-vinegar'

Plug 'justinmk/vim-dirvish'
Plug 'roginfarrer/vim-dirvish-dovish'
"}}}
"{{{ format
Plug 'sbdchd/neoformat'
"}}}
"{{{ file picker
Plug 'junegunn/fzf.vim'
"}}}
"{{{ git
if executable('git')
    Plug 'tpope/vim-fugitive'
    Plug 'airblade/vim-gitgutter'
endif
Plug 'rhysd/conflict-marker.vim'
Plug 'Eliot00/git-lens.vim'
" Plug 'rhysd/git-messenger.vim'
"}}}
"{{{ integration
Plug 'alker0/chezmoi.vim' " chezmoi

" Plug 'raghur/vim-ghost' " browser text input
" Plug 'roxma/nvim-yarp', v:version >= 800 && !has('nvim') ? {} : { 'on': [], 'for': [] }
" Plug 'roxma/vim-hug-neovim-rpc', v:version >= 800 && !has('nvim') ? {} : { 'on': [], 'for': [] }
"
Plug 'tpope/vim-dispatch' " async make
Plug 'voldikss/vim-floaterm' " terminal
"}}}
"{{{ enhance
Plug 'tpope/vim-unimpaired'
Plug 'nelstrom/vim-visual-star-search'
Plug 'zef/vim-cycle' " C-A C-X
Plug 'tommcdo/vim-exchange' " cx exchange text
Plug 'haya14busa/is.vim' " auto nohlsearch
Plug 'andymass/vim-matchup' " enhance asterrisk
Plug 'svermeulen/vim-subversive' " substitute motion
Plug 'AndrewRadev/switch.vim' " regex replace motion
Plug 'AndrewRadev/splitjoin.vim' " gS gJ list split and join
Plug 'wellle/targets.vim' " enhance targets
Plug 'terryma/vim-expand-region' " + expand region
Plug 'mg979/vim-visual-multi' " multiple cursor
Plug 'tpope/vim-surround' " pair markers
" Plug 'vim-polyglot/vim-polyglot' " syntax highlight, conflicts with auto session
Plug 'liuchengxu/vim-which-key' " menu
Plug 'https://gitcode.com/gh_mirrors/vi/vimcdoc' " vim chinese doc
"}}}
"{{{ lisp
if executable('cargo')
    Plug 'eraserhd/parinfer-rust', {'do': 'cargo build --release'}
endif
"}}}
"{{{ markdown
Plug 'godlygeek/tabular'
Plug 'preservim/vim-markdown'
"}}}
"{{{ latex
Plug 'lervag/vimtex', { 'for': 'tex' }
"}}}
"{{{ lsp
if executable('node')
    Plug 'neoclide/coc.nvim', {'branch': 'release'}
endif
" Plug 'yegappan/lsp'
"}}}
"{{{ lint
" Plug 'dense-analysis/ale'
"}}}
"{{{ org
Plug 'jceb/vim-orgmode'
Plug 'tpope/vim-speeddating'
"}}}
"{{{ snippet
Plug 'honza/vim-snippets'
" Plug 'SirVer/ultisnips'
"}}}
"{{{ template
Plug 'aperezdc/vim-template'
"}}}
"{{{ session
Plug 'ourgal/vim-workspace'
"}}}
"{{{ status line
Plug 'itchyny/lightline.vim'
"}}}
"{{{ theme
" Plug 'ghifarit53/tokyonight-vim'
Plug 'https://codeberg.org/mao-yining/vim-catppuccin'
"}}}
call plug#end()
"}}}
