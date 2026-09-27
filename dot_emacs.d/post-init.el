;;; post-init.el --- post init -*- no-byte-compile: t; lexical-binding: t; -*-

(use-package
 undo-fu
 :commands
 (undo-fu-only-undo
  undo-fu-only-redo undo-fu-only-redo-all undo-fu-disable-checkpoint)
 :init
 (global-unset-key (kbd "C-z"))
 (global-set-key (kbd "C-z") 'undo-fu-only-undo)
 (global-set-key (kbd "C-S-z") 'undo-fu-only-redo))

(use-package undo-fu-session :init (undo-fu-session-global-mode 1))

;; Uncomment the following if you are using undo-fu
(setq evil-undo-system 'undo-fu)

(use-package
 evil
 :init
 ;; It has to be defined before evil
 (defvar evil-mode-buffers '())
 (setq evil-want-integration t)
 (setq evil-want-keybinding nil)

 ;; Make :s in visual mode operate only on the actual visual selection
 ;; (character or block), instead of the full lines covered by the selection
 (setq evil-ex-visual-char-range t)
 ;; Use Vim-style regular expressions in search and substitute commands,
 ;; allowing features like \v (very magic), \zs, and \ze for precise matches
 (setq evil-ex-search-vim-style-regexp t)
 ;; Enable automatic horizontal split below
 (setq evil-split-window-below t)
 ;; Enable automatic vertical split to the right
 (setq evil-vsplit-window-right t)
 ;; Disable echoing Evil state to avoid replacing eldoc
 (setq evil-echo-state nil)
 ;; Do not move cursor back when exiting insert state
 (setq evil-move-cursor-back nil)
 ;; Make `v$` exclude the final newline
 (setq evil-v$-excludes-newline t)
 ;; Enable fine-grained undo behavior
 (setq evil-want-fine-undo t)
 ;; Disable wrapping of search around buffer
 (setq evil-search-wrap nil)
 ;; Allow C-h to delete in insert state
 (setq evil-want-C-h-delete t)
 ;; Enable C-u to delete back to indentation in insert state
 (setq evil-want-C-u-delete t)
 ;; Whether Y yanks to the end of the line
 (setq evil-want-Y-yank-to-eol t)

 ;; Start `evil-mode'
 (evil-mode 1))

 ;; :config
 ;; Occasionally, `evil' fails to respect `evil-search-module' when it is
 ;; defined inside the :custom block. This fix ensures the search module
 ;; is correctly set to `evil-search'.
 ;; (setq evil-search-module 'evil-search)
 ;; (evil-select-search-module 'evil-search-module 'evil-search))

(use-package
 evil-collection
 :after evil
 :init
 ;; It has to be defined before evil-collection
 (setq evil-collection-setup-minibuffer t) (evil-collection-init))

(use-package goto-chg :commands (goto-last-change goto-last-change-reverse))

(with-eval-after-load "evil"
  (evil-define-operator
   my-evil-comment-or-uncomment
   (beg end)
   "Toggle comment for the region between BEG and END."
   (interactive "<r>")
   (comment-or-uncomment-region beg end))
  (evil-define-key 'normal 'global (kbd "gc") 'my-evil-comment-or-uncomment))

(use-package
 evil-surround
 :after evil
 :init
 (setq evil-surround-pairs-alist
       '((?\( . ("(" . ")"))
         (?\[ . ("[" . "]")) (?\{ . ("{" . "}"))

         (?\) . ("(" . ")")) (?\] . ("[" . "]")) (?\} . ("{" . "}"))

         (?< . ("<" . ">")) (?> . ("<" . ">"))))
 :config (global-evil-surround-mode 1))

(global-visual-line-mode 1)

(let ((inhibit-redisplay t))
  ;; Disable all active themes
  (mapc #'disable-theme custom-enabled-themes)
  ;; Load the built-in theme
  (load-theme 'modus-vivendi t))

(use-package
 autorevert
 :ensure nil
 :init
 ;; (setq auto-revert-verbose t)
 (setq auto-revert-interval 3)
 (setq auto-revert-remote-files nil)
 (setq auto-revert-use-notify t)
 (setq auto-revert-avoid-polling nil)
 (global-auto-revert-mode 1))

(use-package
 recentf
 :ensure nil
 :init
 (setq recentf-auto-cleanup
       (if (daemonp)
           300
         'never))
 (setq recentf-exclude
       (list
        "\\.tar$"
        "\\.tbz2$"
        "\\.tbz$"
        "\\.tgz$"
        "\\.bz2$"
        "\\.bz$"
        "\\.gz$"
        "\\.gzip$"
        "\\.xz$"
        "\\.zip$"
        "\\.7z$"
        "\\.rar$"
        "COMMIT_EDITMSG\\'"
        "\\.\\(?:gz\\|gif\\|svg\\|png\\|jpe?g\\|bmp\\|xpm\\)$"
        "-autoloads\\.el$"
        "autoload\\.el$"))
 ;; Enable `recentf-mode'
 (recentf-mode 1)

 :config
 ;; A cleanup depth of -90 ensures that `recentf-cleanup' runs before
 ;; `recentf-save-list', allowing stale entries to be removed before the list
 ;; is saved by `recentf-save-list', which is automatically added to
 ;; `kill-emacs-hook' by `recentf-mode'.
 (add-hook 'kill-emacs-hook #'recentf-cleanup -90))

(use-package
 savehist
 :ensure nil
 :init
 (setq history-length 300)
 (setq savehist-autosave-interval 600)
 (savehist-mode 1))

(use-package
 saveplace
 :ensure nil
 :init
 (setq save-place-limit 400)
 (save-place-mode 1))

(setq auto-save-default t)

;; Trigger an auto-save after 300 keystrokes
(setq auto-save-interval 300)

;; Trigger an auto-save 30 seconds of idle time.
(setq auto-save-timeout 30)

(use-package
 corfu
 :custom
 (corfu-auto t) ; Enable auto-completion
 (corfu-auto-prefix 2) ; Minimum characters before popup appears (default is 3)
 (corfu-auto-delay 0.2) ; Delay before popup appears
 (corfu-cycle t) ; Enable cycling through candidates
 (corfu-quit-no-match 'separator) ; Keep popup open when using a separator
 ;; Keybindings specific to the completion popup menu
 :bind
 (:map
  corfu-map
  ("TAB" . corfu-next)
  ([tab] . corfu-next)
  ("S-TAB" . corfu-previous)
  ([backtab] . corfu-previous)
  ("RET" . corfu-insert) ; Insert selected candidate
  ("M-d" . corfu-popupinfo-toggle) ; Toggle documentation popup
  ("M-l" . corfu-popupinfo-location)) ; Jump to source code of candidate
 :init (setq text-mode-ispell-word-completion nil)
 ;; Hide commands in M-x which do not apply to the current mode.
 (setq read-extended-command-predicate #'command-completion-default-include-p)
 ;; Disable Ispell completion function. As an alternative try `cape-dict'.
 (setq tab-always-indent 'complete)

 (global-corfu-mode 1) ; Enable Corfu globally
 (corfu-popupinfo-mode) ; Enable info/documentation popup
 (corfu-history-mode) ; Sort candidates based on history
 (global-completion-preview-mode 1)) ; Enable globally or via hook in your programming modes

(use-package
 nerd-icons-corfu
 :after corfu
 :init
 (add-to-list 'corfu-margin-formatters #'nerd-icons-corfu-formatter))

(use-package
 cape
 :commands (cape-dabbrev cape-file cape-elisp-block)
 :bind ("C-c p" . cape-prefix-map)
 :init
 ;; Add to the global default value of `completion-at-point-functions' which is
 ;; used by `completion-at-point'.
 (add-hook 'completion-at-point-functions #'cape-dabbrev)
 (add-hook 'completion-at-point-functions #'cape-file)
 (add-hook 'completion-at-point-functions #'cape-elisp-block))

(use-package
 vertico
 :init
 ;; (setq vertico-scroll-margin 0) ;; Different scroll margin
 ;; (setq vertico-count 20) ;; Show more candidates
 ;; (setq vertico-resize t) ;; Grow and shrink the Vertico minibuffer
 ;; (setq vertico-cycle t) ;; Enable cycling for `vertico-next/previous'
 (vertico-mode 1))

(use-package
 orderless
 :init
 (setq completion-styles '(orderless basic))
 (setq completion-category-overrides '((file (styles partial-completion))))
 ;; Emacs 31: partial-completion behaves like substring
 (setq completion-pcm-leading-wildcard t))

(use-package
 marginalia
 ;; Bind `marginalia-cycle' locally in the minibuffer.  To make the binding
 ;; available in the *Completions* buffer, add it to the
 ;; `completion-list-mode-map'.
 :bind (:map minibuffer-local-map ("M-A" . marginalia-cycle))

 ;; The :init section is always executed.
 :init

 ;; Marginalia must be activated in the :init section of use-package such that
 ;; the mode gets enabled right away. Note that this forces loading the
 ;; package.
 (marginalia-mode 1))

(use-package
 embark
 :bind
 (("C-." . embark-act) ;; pick some comfortable binding
  ("C-;" . embark-dwim) ;; good alternative: M-.
  ("C-h B" . embark-bindings)) ;; alternative for `describe-bindings'

 :init

 ;; Optionally replace the key help with a completing-read interface
 (setq prefix-help-command #'embark-prefix-help-command)

 ;; Show the Embark target at point via Eldoc. You may adjust the
 ;; Eldoc strategy, if you want to see the documentation from
 ;; multiple providers. Beware that using this can be a little
 ;; jarring since the message shown in the minibuffer can be more
 ;; than one line, causing the modeline to move up and down:

 ;; (add-hook 'eldoc-documentation-functions #'embark-eldoc-first-target)
 ;; (setq eldoc-documentation-strategy #'eldoc-documentation-compose-eagerly)

 ;; Add Embark to the mouse context menu. Also enable `context-menu-mode'.
 ;; (context-menu-mode 1)
 ;; (add-hook 'context-menu-functions #'embark-context-menu 100)

 :config
 ;; Hide the mode line of the Embark live/completions buffers
 (add-to-list
  'display-buffer-alist
  '("\\`\\*Embark Collect \\(Live\\|Completions\\)\\*"
    nil
    (window-parameters (mode-line-format . none)))))

;; overlap vim default C-. keybinding
(with-eval-after-load 'evil-maps
  (define-key evil-normal-state-map (kbd "C-.") #'embark-act)
  (define-key evil-visual-state-map (kbd "C-.") #'embark-act)
  (define-key evil-insert-state-map (kbd "C-.") #'embark-act))

(use-package embark-consult)

(use-package
 consult
 ;; Replace bindings. Lazily loaded by `use-package'.
 :bind
 ( ;; C-c bindings in `mode-specific-map'
  ("C-c M-x" . consult-mode-command)
  ("C-c h" . consult-history)
  ("C-c k" . consult-kmacro)
  ("C-c m" . consult-man)
  ("C-c i" . consult-info)
  ([remap Info-search] . consult-info)
  ;; C-x bindings in `ctl-x-map'
  ("C-x M-:" . consult-complex-command) ;; orig. repeat-complex-command
  ("C-x b" . consult-buffer) ;; orig. switch-to-buffer
  ("C-x 4 b" . consult-buffer-other-window) ;; orig. switch-to-buffer-other-window
  ("C-x 5 b" . consult-buffer-other-frame) ;; orig. switch-to-buffer-other-frame
  ("C-x t b" . consult-buffer-other-tab) ;; orig. switch-to-buffer-other-tab
  ("C-x r b" . consult-bookmark) ;; orig. bookmark-jump
  ("C-x p b" . consult-project-buffer) ;; orig. project-switch-to-buffer
  ;; Custom M-# bindings for fast register access
  ("M-#" . consult-register-load)
  ("M-'" . consult-register-store) ;; orig. abbrev-prefix-mark (unrelated)
  ("C-M-#" . consult-register)
  ;; Other custom bindings
  ("M-y" . consult-yank-pop) ;; orig. yank-pop
  ;; M-g bindings in `goto-map'
  ("M-g e" . consult-compile-error)
  ("M-g r" . consult-grep-match)
  ("M-g f" . consult-flymake) ;; Alternative: consult-flycheck
  ("M-g g" . consult-goto-line) ;; orig. goto-line
  ("M-g M-g" . consult-goto-line) ;; orig. goto-line
  ("M-g o" . consult-outline) ;; Alternative: consult-org-heading
  ("M-g m" . consult-mark)
  ("M-g k" . consult-global-mark)
  ("M-g i" . consult-imenu)
  ("M-g I" . consult-imenu-multi)
  ;; M-s bindings in `search-map'
  ("M-s d" . consult-find) ;; Alternative: consult-fd
  ("M-s c" . consult-locate)
  ("M-s g" . consult-grep)
  ("M-s G" . consult-git-grep)
  ("M-s r" . consult-ripgrep)
  ("M-s l" . consult-line)
  ("M-s L" . consult-line-multi)
  ("M-s k" . consult-keep-lines)
  ("M-s u" . consult-focus-lines)
  ;; Isearch integration
  ("M-s e" . consult-isearch-history)
  :map
  isearch-mode-map
  ("M-e" . consult-isearch-history) ;; orig. isearch-edit-string
  ("M-s e" . consult-isearch-history) ;; orig. isearch-edit-string
  ("M-s l" . consult-line) ;; needed by consult-line to detect isearch
  ("M-s L" . consult-line-multi) ;; needed by consult-line to detect isearch
  ;; Minibuffer history
  :map
  minibuffer-local-map
  ("M-s" . consult-history) ;; orig. next-matching-history-element
  ("M-r" . consult-history)) ;; orig. previous-matching-history-element

 ;; The :init configuration is always executed (Not lazy)
 :init

 ;; Tweak the register preview for `consult-register-load',
 ;; `consult-register-store' and the built-in commands.  This improves the
 ;; register formatting, adds thin separator lines, register sorting and hides
 ;; the window mode line.
 (advice-add #'register-preview :override #'consult-register-window)
 (setq register-preview-delay 0.5)

 ;; Use Consult to select xref locations with preview
 (setq
  xref-show-xrefs-function #'consult-xref
  xref-show-definitions-function #'consult-xref)

 ;; Configure other variables and modes in the :config section,
 ;; after lazily loading the package.
 :config

 ;; Optionally configure preview. The default value
 ;; is 'any, such that any key triggers the preview.
 ;; (setq consult-preview-key 'any)
 ;; (setq consult-preview-key "M-.")
 ;; (setq consult-preview-key '("S-<down>" "S-<up>"))
 ;; For some commands and buffer sources it is useful to configure the
 ;; :preview-key on a per-command basis using the `consult-customize' macro.
 (consult-customize
  consult-theme
  :preview-key
  '(:debounce 0.2 any)
  consult-ripgrep
  consult-git-grep
  consult-grep
  consult-man
  consult-bookmark
  consult-recent-file
  consult-xref
  consult-source-bookmark
  consult-source-file-register
  consult-source-recent-file
  consult-source-project-recent-file
  ;; :preview-key "M-."
  :preview-key '(:debounce 0.4 any))

 ;; Optionally configure the narrowing key.
 ;; Both < and C-+ work reasonably well.
 (setq consult-narrow-key "<") ;; "C-+"

 ;; Optionally make narrowing help available in the minibuffer.
 ;; You may want to use `embark-prefix-help-command' or which-key instead.
 ;; (keymap-set consult-narrow-map (concat consult-narrow-key " ?") #'consult-narrow-help)
 )

(use-package
 easysession
 ;; ':demand t' ensures the package is loaded immediately upon startup
 :demand t

 :config
 ;; Key mappings
 (global-set-key (kbd "C-c sl") #'easysession-switch-to) ; Load session
 (global-set-key (kbd "C-c ss") #'easysession-save) ; Save session
 (global-set-key (kbd "C-c sL") #'easysession-switch-to-and-restore-geometry)
 (global-set-key (kbd "C-c sr") #'easysession-rename)
 (global-set-key (kbd "C-c sR") #'easysession-reset)
 (global-set-key (kbd "C-c su") #'easysession-unload)
 (global-set-key (kbd "C-c sd") #'easysession-delete)

 ;; Save every 10 minutes
 (setq easysession-save-interval (* 10 60))

 ;; Save the current session when using `easysession-switch-to'
 (setq easysession-switch-to-save-session t)

 ;; Do not exclude the current session when switching sessions
 (setq easysession-switch-to-exclude-current nil)

 ;; Display the active session name in the mode-line lighter.
 ;; (setq easysession-save-mode-lighter-show-session-name t)

 ;; Optionally, the session name can be shown in the modeline info area:
 ;; (setq easysession-mode-line-misc-info t)
 ;; non-nil: Make `easysession-setup' load the session automatically.
 ;; (nil: session is not loaded automatically; the user can load it manually.)
 (setq easysession-setup-load-session t)

 ;; The `easysession-setup' function adds hooks:
 ;; - To enable automatic session loading during `emacs-startup-hook', or
 ;;   `server-after-make-frame-hook' when running in daemon mode.
 ;; - To save the session at regular intervals, and when Emacs exits.
 (easysession-setup))

(set-face-attribute 'default nil
                    :height 130
                    :weight 'normal
                    :family "Maple Mono NF CN")

(use-package
 markdown-mode
 :commands (gfm-mode gfm-view-mode markdown-mode markdown-view-mode)
 :mode
 (("\\.markdown\\'" . markdown-mode)
  ("\\.md\\'" . markdown-mode)
  ("README\\.md\\'" . gfm-mode))
 :bind (:map markdown-mode-map ("C-c C-e" . markdown-do)))

(use-package
 markdown-toc
 :commands
 (markdown-toc-generate-toc
  markdown-toc-generate-or-refresh-toc
  markdown-toc-delete-toc
  markdown-toc--toc-already-present-p)
 :init (setq markdown-toc-header-toc-title "**Table of Contents**"))

(use-package
 kirigami
 :commands
 (kirigami-open-fold
  kirigami-open-fold-rec
  kirigami-close-fold
  kirigami-toggle-fold
  kirigami-open-folds
  kirigami-close-folds-except-current
  kirigami-close-folds)

 :bind
 (("C-c z o" . kirigami-open-fold) ; Open fold at point
  ("C-c z O" . kirigami-open-fold-rec) ; Open fold recursively
  ("C-c z r" . kirigami-open-folds) ; Open all folds
  ("C-c z c" . kirigami-close-fold) ; Close fold at point
  ("C-c z m" . kirigami-close-folds) ; Close all folds
  ("C-c z a" . kirigami-toggle-fold)) ; Toggle fold at point

 :init (kirigami-global-mode 1))

;; Uncomment the following if you are an `evil-mode' user:
(with-eval-after-load 'evil
  (define-key evil-normal-state-map "zo" 'kirigami-open-fold)
  (define-key evil-normal-state-map "zO" 'kirigami-open-fold-rec)
  (define-key evil-normal-state-map "zc" 'kirigami-close-fold)
  (define-key evil-normal-state-map "za" 'kirigami-toggle-fold)
  (define-key evil-normal-state-map "zr" 'kirigami-open-folds)
  (define-key evil-normal-state-map "zm" 'kirigami-close-folds))

(use-package
 outline
 :ensure nil
 :commands outline-minor-mode
 :hook
 ( ;; Use " ▼" instead of the default ellipsis "..." for folded text to make
  ;; folds more visually distinctive and readable.
  (outline-minor-mode
   .
   (lambda ()
     (let* ((display-table (or buffer-display-table (make-display-table)))
            (face-offset (* (face-id 'shadow) (ash 1 22)))
            (value (vconcat (mapcar (lambda (c) (+ face-offset c)) " ▼"))))
       (set-display-table-slot display-table 'selective-display value)
       (setq buffer-display-table display-table))))))

;; Enable the mode
(add-hook 'emacs-lisp-mode-hook #'outline-minor-mode)
(add-hook 'lisp-mode-hook #'outline-minor-mode)
(add-hook 'conf-mode-hook #'outline-minor-mode)
(add-hook 'markdown-mode-hook #'outline-minor-mode)
(add-hook 'diff-mode-hook #'outline-minor-mode)

(add-hook 'c-mode-hook #'hs-minor-mode)
(add-hook 'c++-mode-hook #'hs-minor-mode)
(add-hook 'java-mode-hook #'hs-minor-mode)
(add-hook 'sh-mode-hook #'hs-minor-mode)
(add-hook 'html-mode-hook #'hs-minor-mode)

(use-package
 outline-indent
 :commands outline-indent-minor-mode
 :init (setq outline-indent-ellipsis " ▼"))

;; Python
(add-hook 'python-mode-hook #'outline-indent-minor-mode)
(add-hook 'python-ts-mode-hook #'outline-indent-minor-mode)

;; Yaml
(add-hook 'yaml-mode-hook #'outline-indent-minor-mode)
(add-hook 'yaml-ts-mode-hook #'outline-indent-minor-mode)

;; Haskell
(add-hook 'haskell-mode-hook #'outline-indent-minor-mode)

(use-package
 treesit-fold
 :commands
 (treesit-fold-close
  treesit-fold-close-all
  treesit-fold-open
  treesit-fold-toggle
  treesit-fold-open-all
  treesit-fold-mode
  global-treesit-fold-mode
  treesit-fold-open-recursively
  treesit-fold-line-comment-mode)

 :init
 (setq treesit-fold-line-count-show t)
 (setq treesit-fold-line-count-format " ▼")

 :config
 (set-face-attribute 'treesit-fold-replacement-face nil
                     :foreground "#808080"
                     :box nil
                     :weight 'bold))

;; A few examples
(add-hook 'c-ts-mode-hook #'treesit-fold-mode)
(add-hook 'c++-ts-mode-hook #'treesit-fold-mode)
(add-hook 'php-ts-mode-hook #'treesit-fold-mode)
(add-hook 'css-ts-mode-hook #'treesit-fold-mode)
(add-hook 'html-ts-mode-hook #'treesit-fold-mode)
(add-hook 'bash-ts-mode-hook #'treesit-fold-mode)

(use-package
 apheleia
 :commands (apheleia-mode apheleia-global-mode)
 :hook ((prog-mode . apheleia-mode)))

(setq-default display-line-numbers-type 'relative)
(global-display-line-numbers-mode 1)

(use-package
 dumb-jump
 :commands dumb-jump-xref-activate
 :init
 ;; Register `dumb-jump' as an xref backend so it integrates with
 ;; `xref-find-definitions'. A priority of 80 ensures it is used only when no
 ;; more specific backend is available.
 (with-eval-after-load 'xref
   (add-hook 'xref-backend-functions #'dumb-jump-xref-activate 80))

 (setq dumb-jump-aggressive nil)
 ;; (setq dumb-jump-quiet t)

 ;; Number of seconds a rg/grep/find command can take before being warned to
 ;; use ag and config.
 (setq dumb-jump-max-find-time 3)

 ;; Use `completing-read' so that selection of jump targets integrates with the
 ;; active completion framework (e.g., Vertico, Ivy, Helm, Icomplete),
 ;; providing a consistent minibuffer-based interface whenever multiple
 ;; definitions are found.
 (setq dumb-jump-selector 'completing-read)

 :config
 ;; If ripgrep is available, force `dumb-jump' to use it because it is
 ;; significantly faster and more accurate than the default searchers (grep,
 ;; ag, etc.).
 (when (executable-find "rg")
   (setq dumb-jump-force-searcher 'rg)
   (setq dumb-jump-prefer-searcher 'rg)))

;; The official collection of snippets for yasnippet.
(use-package yasnippet-snippets)

(use-package
 yasnippet
 :after yasnippet-snippets
 :init
 (setq yas-also-auto-indent-first-line t) ; Indent first line of snippet
 (setq yas-also-indent-empty-lines t)
 (setq yas-snippet-revival nil) ; Setting this to t causes issues with undo
 (setq yas-wrap-around-region nil) ; Do not wrap region when expanding snippets
 (setq yas-indent-line 'fixed) ; Do not auto-indent snippet content
 ;; (setq yas-triggers-in-field nil)  ; Disable nested snippet expansion
 ;; (setq yas-prompt-functions '(yas-no-prompt))  ; No prompt for snippet choices

 ;; Suppress verbose messages
 (setq yas-verbosity 0)

 (yas-global-mode 1))

(use-package
 stripspace
 :commands stripspace-local-mode

 ;; Enable for prog-mode-hook, text-mode-hook, conf-mode-hook
 :hook
 ((prog-mode . stripspace-local-mode)
  (text-mode . stripspace-local-mode)
  (conf-mode . stripspace-local-mode))

 :init
 ;; The `stripspace-only-if-initially-clean' option:
 ;; - nil to always delete trailing whitespace.
 ;; - Non-nil to only delete whitespace when the buffer is clean initially.
 ;; (The initial cleanliness check is performed when `stripspace-local-mode'
 ;; is enabled.)
 (setq stripspace-only-if-initially-clean nil)

 ;; Enabling `stripspace-restore-column' preserves the cursor's column position
 ;; even after stripping spaces. This is useful in scenarios where you add
 ;; extra spaces and then save the file. Although the spaces are removed in the
 ;; saved file, the cursor remains in the same position, ensuring a consistent
 ;; editing experience without affecting cursor placement.
 (setq stripspace-restore-column t))

(use-package
 diff-hl
 :commands (diff-hl-mode global-diff-hl-mode)
 :hook ((prog-mode . diff-hl-mode) (org-mode . diff-hl-mode))
 :init
 (setq diff-hl-flydiff-delay 0.4) ; Faster
 (setq diff-hl-show-staged-changes nil) ; Realtime feedback
 (setq diff-hl-update-async t) ; Do not block Emacs
 (setq diff-hl-global-modes '(not pdf-view-mode image-mode))
 (add-hook 'magit-post-refresh-hook #'diff-hl-magit-post-refresh))

(use-package
 org
 :commands (org-mode org-version)
 :mode ("\\.org\\'" . org-mode)
 :hook
 (org-mode
  .
  (lambda ()
    (setq-local electric-pair-inhibit-predicate
                (lambda (c)
                  (if (char-equal c ?<)
                      t
                    (electric-pair-default-inhibit c))))))
 :init
 (setq org-hide-leading-stars t)
 (setq org-startup-indented t)
 (setq org-adapt-indentation nil)
 (setq org-edit-src-content-indentation 0)
 ;; (setq org-fontify-done-headline t)
 ;; (setq org-fontify-todo-headline t)
 ;; (setq org-fontify-whole-heading-line t)
 ;; (setq org-fontify-quote-and-verse-blocks t)
 (setq org-startup-truncated t))

(use-package
 org-appear
 :commands org-appear-mode
 :hook (org-mode . org-appear-mode))

(use-package
 org-auto-tangle
 :ensure t
 :defer t
 :hook (org-mode . org-auto-tangle-mode)
 :config
 ;; Optional: Set to t if you want ALL org files to auto-tangle by default
 (setq org-auto-tangle-default t))

(use-package
 eglot
 :ensure nil
 :commands (eglot-ensure eglot-rename eglot-format-buffer))

(add-hook 'python-mode-hook #'eglot-ensure)
(add-hook 'python-ts-mode-hook #'eglot-ensure)
(setq-default eglot-workspace-configuration
              `(:pylsp
                (:plugins
                 ( ;; Fix imports and syntax using `eglot-format-buffer`
                  :isort
                  (:enabled t)
                  :autopep8 (:enabled t)

                  ;; Syntax checkers (works with Flymake)
                  :pylint (:enabled t)
                  :pycodestyle (:enabled t)
                  :flake8 (:enabled t)
                  :pyflakes (:enabled t)
                  :pydocstyle (:enabled t)
                  :mccabe (:enabled t)

                  :yapf (:enabled :json-false)
                  :rope_autoimport (:enabled :json-false)))))

(use-package
 buffer-terminator
 :init
 ;; Enable/Disable verbose mode to log buffer cleanup events
 (setq buffer-terminator-verbose nil)

 ;; Set the inactivity timeout (in seconds) after which buffers are considered
 ;; inactive (default is 30 minutes):
 (setq buffer-terminator-inactivity-timeout (* 30 60)) ; 30 minutes

 ;; Define how frequently the cleanup process should run (default is every 10
 ;; minutes):
 (setq buffer-terminator-interval (* 10 60)) ; 10 minutes

 (buffer-terminator-mode 1))

(use-package
 treemacs
 :commands
 (treemacs
  treemacs-select-window
  treemacs-delete-other-windows
  treemacs-select-directory
  treemacs-bookmark
  treemacs-find-file
  treemacs-find-tag)

 :bind
 (:map
  global-map
  ("M-0" . treemacs-select-window)
  ("C-x t 1" . treemacs-delete-other-windows)
  ("C-x t t" . treemacs)
  ("C-x t d" . treemacs-select-directory)
  ("C-x t B" . treemacs-bookmark)
  ("C-x t C-t" . treemacs-find-file)
  ("C-x t M-t" . treemacs-find-tag))

 :init
 (with-eval-after-load 'winum
   (define-key winum-keymap (kbd "M-0") #'treemacs-select-window))

 :config
 (setq
  treemacs-collapse-dirs
  (if treemacs-python-executable
      3
    0)
  treemacs-deferred-git-apply-delay 0.5
  treemacs-directory-name-transformer #'identity
  treemacs-display-in-side-window t
  treemacs-eldoc-display 'simple
  treemacs-file-event-delay 2000
  treemacs-file-extension-regex treemacs-last-period-regex-value
  treemacs-file-follow-delay 0.2
  treemacs-file-name-transformer #'identity
  treemacs-follow-after-init t
  treemacs-expand-after-init t
  treemacs-find-workspace-method 'find-for-file-or-pick-first
  treemacs-git-command-pipe ""
  treemacs-goto-tag-strategy 'refetch-index
  treemacs-header-scroll-indicators '(nil . "^^^^^^")
  treemacs-hide-dot-git-directory t
  treemacs-indentation 2
  treemacs-indentation-string " "
  treemacs-is-never-other-window nil
  treemacs-max-git-entries 5000
  treemacs-missing-project-action 'ask
  treemacs-move-files-by-mouse-dragging t
  treemacs-move-forward-on-expand nil
  treemacs-no-png-images nil
  treemacs-no-delete-other-windows t
  treemacs-project-follow-cleanup nil
  treemacs-persist-file (expand-file-name ".cache/treemacs-persist" user-emacs-directory)
  treemacs-position 'left
  treemacs-read-string-input 'from-child-frame
  treemacs-recenter-distance 0.1
  treemacs-recenter-after-file-follow nil
  treemacs-recenter-after-tag-follow nil
  treemacs-recenter-after-project-jump 'always
  treemacs-recenter-after-project-expand 'on-distance
  treemacs-litter-directories '("/node_modules" "/.venv" "/.cask")
  treemacs-project-follow-into-home nil
  treemacs-show-cursor nil
  treemacs-show-hidden-files t
  treemacs-silent-filewatch nil
  treemacs-silent-refresh nil
  treemacs-sorting 'alphabetic-asc
  treemacs-select-when-already-in-treemacs 'move-back
  treemacs-space-between-root-nodes t
  treemacs-tag-follow-cleanup t
  treemacs-tag-follow-delay 1.5
  treemacs-text-scale nil
  treemacs-user-mode-line-format nil
  treemacs-user-header-line-format nil
  treemacs-wide-toggle-width 70
  treemacs-width 35
  treemacs-width-increment 1
  treemacs-width-is-initially-locked t
  treemacs-workspace-switch-cleanup nil)

 ;; The default width and height of the icons is 22 pixels. If you are
 ;; using a Hi-DPI display, uncomment this to double the icon size.
 ;; (treemacs-resize-icons 44)

 (treemacs-follow-mode t)
 (treemacs-filewatch-mode t)
 (treemacs-fringe-indicator-mode 'always)

 ;;(when treemacs-python-executable
 ;;  (treemacs-git-commit-diff-mode t))

 (pcase (cons
         (not (null (executable-find "git")))
         (not (null treemacs-python-executable)))
   (`(t . t) (treemacs-git-mode 'deferred))
   (`(t . _) (treemacs-git-mode 'simple)))

 (treemacs-hide-gitignored-files-mode nil))

(use-package treemacs-evil :after (treemacs evil))
;;
;; (use-package treemacs-icons-dired
;;   :hook (dired-mode . treemacs-icons-dired-enable-once))
;;
;; (use-package treemacs-tab-bar  ; treemacs-tab-bar if you use tab-bar-mode
;;   :after (treemacs)
;;   :config (treemacs-set-scope-type 'Tabs))
;;
;; (treemacs-start-on-boot)

(use-package
 helpful
 :commands
 (helpful-callable
  helpful-variable
  helpful-key
  helpful-command
  helpful-at-point
  helpful-function)
 :bind
 ([remap describe-command] . helpful-command)
 ([remap describe-function] . helpful-callable)
 ([remap describe-key] . helpful-key)
 ([remap describe-symbol] . helpful-symbol)
 ([remap describe-variable] . helpful-variable)
 :init (setq helpful-max-buffers 7))

(use-package
 avy
 :commands (avy-goto-char avy-goto-char-2 avy-next)
 :init (global-set-key (kbd "C-'") 'avy-goto-char-2))

(use-package
 bufferfile
 :commands (bufferfile-copy bufferfile-rename bufferfile-delete)
 :init
 ;; If non-nil, display messages during file renaming operations
 (setq bufferfile-verbose nil)

 ;; If non-nil, enable using version control (VC) when available
 (setq bufferfile-use-vc nil)

 ;; Specifies the action taken after deleting a file and killing its buffer.
 (setq bufferfile-delete-switch-to 'parent-directory))

;; Enables automatic indentation of code while typing
(use-package
 aggressive-indent
 :commands aggressive-indent-mode
 :hook (emacs-lisp-mode . aggressive-indent-mode))

;; Highlights function and variable definitions in Emacs Lisp mode
(use-package
 highlight-defined
 :commands highlight-defined-mode
 :hook (emacs-lisp-mode . highlight-defined-mode))

(editorconfig-mode 1)

;; Prevent parenthesis imbalance
(use-package
 paredit
 :commands paredit-mode
 :hook (emacs-lisp-mode . paredit-mode)
 :config (define-key paredit-mode-map (kbd "RET") nil))

;; For paredit+Evil mode users: enhances paredit with Evil mode compatibility
;; --------------------------------------------------------------------------
(use-package
 enhanced-evil-paredit
 :commands enhanced-evil-paredit-mode
 :hook (paredit-mode . enhanced-evil-paredit-mode))

;; Configure the `tab-bar-show` variable to 1 to display the tab bar exclusively
;; when multiple tabs are open:
(setopt tab-bar-show 1)

(use-package
 server
 :ensure nil
 :if (not (daemonp))
 :preface
 (defun my-server-start ()
   "Start the Emacs server if no server process is currently active."
   (unless (server-running-p)
     (server-start)))
 :init
 ;; Defer starting the server until after Emacs has finished initializing
 (add-hook 'emacs-startup-hook #'my-server-start))

(use-package elec-pair :ensure nil :init (electric-pair-mode 1))

(fringe-mode (frame-char-width))

(unless (and (eq window-system 'mac)
             (bound-and-true-p mac-carbon-version-string))
  ;; Enables `pixel-scroll-precision-mode' on all operating systems and Emacs
  ;; versions, except for emacs-mac.
  ;;
  ;; Enabling `pixel-scroll-precision-mode' is unnecessary with emacs-mac, as
  ;; this version of Emacs natively supports smooth scrolling.
  ;; https://bitbucket.org/mituharu/emacs-mac/commits/65c6c96f27afa446df6f9d8eff63f9cc012cc738
  (setq pixel-scroll-precision-use-momentum nil) ; Precise/smoother scrolling
  (pixel-scroll-precision-mode 1))

(window-divider-mode 1)

(setq enable-local-variables :safe)

(use-package
 buffer-guardian
 :init
 ;; When non-nil, include remote files in the auto-save process
 (setq buffer-guardian-inhibit-saving-remote-files t)

 ;; When non-nil, buffers visiting nonexistent files are not saved
 (setq buffer-guardian-inhibit-saving-nonexistent-files nil)

 ;; Save the buffer even if the window change results in the same buffer
 (setq buffer-guardian-save-on-same-buffer-window-change t)

 ;; Non-nil to enable verbose mode to log when a buffer is automatically saved
 (setq buffer-guardian-verbose nil)

 ;; Save all buffers after N seconds of user idle time. (Disabled by default)
 ;; (setq buffer-guardian-save-all-buffers-idle 30)

 ;; Save all buffers every N seconds. (Disabled by default)
 ;; (setq buffer-guardian-save-all-buffers-interval (* 60 30))

 (buffer-guardian-mode 1))

(use-package
 evil-matchit
 :commands turn-on-evil-matchit-mode
 :hook (prog-mode . turn-on-evil-matchit-mode)

 :init
 ;; Setting this to t disables the advanced Python matching algorithm.
 ;; Set to nil if you prefer the advanced block-matching behavior in Python.
 (setq evilmi-always-simple-jump t)

 ;; Uncomment the following if you are an `evil-mode' user:
 (with-eval-after-load 'evil
   (require 'evil-matchit-evil-setup))

 :config
 ;; Because evil-matchit maps its rules to traditional major modes by default,
 ;; we must manually associate the new tree-sitter modes with their respective
 ;; matching rules until the package incorporates them natively.
 (when (fboundp 'evilmi-load-plugin-rules)
   (evilmi-load-plugin-rules '(cmake-ts-mode) '(cmake))
   (evilmi-load-plugin-rules '(c-ts-mode c++-ts-mode) '(c simple))
   (evilmi-load-plugin-rules '(bash-ts-mode) '(simple sh))
   (evilmi-load-plugin-rules '(css-ts-mode) '(simple))
   (evilmi-load-plugin-rules '(php-ts-mode) '(simple template html))
   (evilmi-load-plugin-rules '(lua-ts-mode) '(simple script))
   (evilmi-load-plugin-rules '(python-ts-mode) '(simple python))
   (evilmi-load-plugin-rules '(yaml-ts-mode) '(simple yaml))))

(use-package
 tmpl-mode
 :vc (:url "https://github.com/Lindydancer/tmpl-mode")
 :init (tmpl-global-mode))

;; Constrain vertical cursor movement to lines within the buffer
(setq dired-movement-style 'bounded-files)

;; Dired buffers: Automatically hide file details (permissions, size,
;; modification date, etc.) and all the files in the `dired-omit-files' regular
;; expression for a cleaner display.
(add-hook 'dired-mode-hook #'dired-hide-details-mode)

;; Hide files from dired
(setq dired-omit-files
      (concat
       "\\`[.]\\'"
       "\\|\\(?:\\.js\\)?\\.meta\\'"
       "\\|\\.\\(?:elc\\|a\\|o\\|pyc\\|pyo\\|swp\\|class\\)\\'"
       "\\|^\\.DS_Store\\'"
       "\\|^\\.\\(?:svn\\|git\\)\\'"
       "\\|^\\.ccls-cache\\'"
       "\\|^__pycache__\\'"
       "\\|^\\.project\\(?:ile\\)?\\'"
       "\\|^flycheck_.*"
       "\\|^flymake_.*"))
(add-hook 'dired-mode-hook #'dired-omit-mode)

;; dired: Group directories first
(with-eval-after-load 'dired
  (let ((args "--group-directories-first -ahlv"))
    (when (or (eq system-type 'darwin) (eq system-type 'berkeley-unix))
      (if-let* ((gls (executable-find "gls")))
          (setq insert-directory-program gls)
        (setq args nil)))
    (when args
      (setq dired-listing-switches args))))

(evil-define-key 'normal 'global (kbd "-") 'dired-jump)

(use-package nerd-icons-dired :hook (dired-mode . nerd-icons-dired-mode))

;; Enable the built-in which-key mode
(which-key-mode 1)

;; Customize the pop-up behavior and layout
(setq which-key-idle-delay 0.3) ;; Pop up after 0.3 seconds of hesitation

(setq which-key-enable-extended-define-key t)

(evil-define-key 'normal 'global (kbd "SPC SPC") '("Find file" . project-find-file))

(use-package
 magit
 :ensure t
 :bind
 ( ;; Global entry points into Magit
  ("C-x g" . magit-status)
  ("C-c g g" . magit-status)
  ("C-c g d" . magit-dispatch)
  ("C-c g f" . magit-file-dispatch))

 :config
 ;; 1. Window Management (Open magit-status in full screen)
 (setq magit-display-buffer-function #'magit-display-buffer-fullframe-status-v1)

 ;; 2. Automatic Reverts
 ;; Also automatically refresh Magit when local Git states alter
 (setq magit-auto-revert-mode t)

 ;; 3. Better Defaults & Layouts
 ;; Hide the VC mode-line indicator to keep the bar clean
 (setq vc-handled-backends nil)
 ;; Don't ask to save modified file buffers before running status
 (setq magit-save-repository-buffers 'dontask)

 ;; 4. Windows Performance Tweaks (Only runs on MS Windows)
 (when (eq system-type 'windows-nt)
   (setq magit-git-global-arguments
         (append
          magit-git-global-arguments
          '("-c"
            "core.preloadindex=true"
            "-c"
            "core.fscache=true"
            "-c"
            "gc.auto=256")))))
(setq magit-format-file-function #'magit-format-file-nerd-icons)

(evil-define-key 'normal 'global (kbd "SPC g g") 'magit-status)

;; Support for Git files (.gitconfig, .gitignore, .gitattributes...)
(use-package
 git-modes
 :commands (gitattributes-mode gitconfig-mode gitignore-mode)
 :mode
 (("/\\.gitignore\\'" . gitignore-mode)
  ("/info/exclude\\'" . gitignore-mode)
  ("/git/ignore\\'" . gitignore-mode)

  ("/\\.gitconfig\\'" . gitconfig-mode)
  ("/\\.git/config\\'" . gitconfig-mode)
  ("/modules/.*/config\\'" . gitconfig-mode)
  ("/git/config\\'" . gitconfig-mode)
  ("/\\.gitmodules\\'" . gitconfig-mode)
  ("/etc/gitconfig\\'" . gitconfig-mode)

  ("/\\.gitattributes\\'" . gitattributes-mode)
  ("/info/attributes\\'" . gitattributes-mode)
  ("/git/attributes\\'" . gitattributes-mode)))

(use-package
 yaml-mode
 :commands yaml-mode
 :mode (("\\.yaml\\'" . yaml-mode) ("\\.yml\\'" . yaml-mode)))

(use-package
 dockerfile-mode
 :commands dockerfile-mode
 :mode ("Dockerfile\\'" . dockerfile-mode))

(use-package gnuplot :commands gnuplot-mode :mode ("\\.gp\\'" . gnuplot-mode))

(use-package lua-mode :commands lua-mode :mode ("\\.lua\\'" . lua-mode))

(use-package jinja2-mode :commands jinja2-mode :mode ("\\.j2\\'" . jinja2-mode))

(use-package
 csv-mode
 :commands (csv-mode csv-align-mode csv-guess-set-separator)
 :mode ("\\.csv\\'" . csv-mode)
 :hook ((csv-mode . csv-align-mode) (csv-mode . csv-guess-set-separator))
 :init
 (setq csv-align-max-width 100)
 (setq csv-separators '("," ";" " " "|" "\t")))

(use-package go-mode :commands go-mode :mode ("\\.go\\'" . go-mode))

(use-package
 rust-mode
 :commands rust-mode
 :mode ("\\.rs\\'" . rust-mode)
 :init (setq rust-indent-offset 2))

(use-package
 crontab-mode
 :commands crontab-mode
 :mode ("/crontab\\(\\.X*[[:alnum:]]+\\)?\\'" . crontab-mode))

(use-package
 nginx-mode
 :commands nginx-mode
 :mode
 (("nginx\\.conf\\'" . nginx-mode) ("/nginx/.+\\.conf\\'" . nginx-mode)))

(use-package hcl-mode :commands hcl-mode :mode ("\\.hcl\\'" . hcl-mode))

(use-package nix-mode :commands nix-mode :mode ("\\.nix\\'" . nix-mode))

(use-package fish-mode :commands fish-mode :mode ("\\.fish\\'" . fish-mode))

(use-package
 vimrc-mode
 :commands vimrc-mode
 :mode ("\\.vim\\(rc\\)?\\'" . vimrc-mode))

(use-package
  json-mode
  :commands json-mode
  :mode ("\\.json\\(c\\)\\'" . json-mode))

(use-package
 jenkinsfile-mode
 :commands jenkinsfile-mode
 :mode ("Jenkinsfile\\'" . jenkinsfile-mode))

(use-package
 indent-bars
 :ensure t
 :hook ((prog-mode . indent-bars-mode))
 :custom
 ;; Optional: Customize style presets
 (indent-bars-width-frac 0.15) ; Width of the bar relative to a character width
 (indent-bars-pad-frac 0.1) ; Offset padding inside the character space

 ;; Optional: Better compatibility for terminal/certain windows
 ;; (indent-bars-prefer-character t)        ; Force char-based display instead of stipples
 )

(use-package
 elisp-autofmt
 :ensure t
 :commands (elisp-autofmt-mode elisp-autofmt-buffer)
 :hook (emacs-lisp-mode . elisp-autofmt-mode)
 :init
 ;; By default, the minor mode only formats on save if an empty `.elisp-autofmt`
 ;; file exists in the project root. Change to 'always to format all elisp files.
 (setq elisp-autofmt-on-save-p 'always)

 :config
 ;; Style customization ('native uses standard Emacs indentation rules)
 (setq elisp-autofmt-style 'native)

 ;; Keep a maximum of 2 consecutive empty lines
 (setq elisp-autofmt-empty-line-max 2)

 ;; Format single-quoted S-expressions (set to nil to only keep indentation)
 (setq elisp-autofmt-format-quoted t))

(use-package
 rainbow-delimiters
 :ensure t
 :hook (prog-mode . rainbow-delimiters-mode))

(use-package
 nov
 :ensure t
 :mode ("\\.epub\\'" . nov-mode)
 :config
 ;; Adjust text width for comfortable reading
 (setq nov-text-width 80)

 ;; Use a clean, variable-pitch font for the book text
 (defun my-nov-font-setup ()
   (face-remap-add-relative 'default :family "Maple Mono NF CN" :height 120))

 (add-hook 'nov-mode-hook 'my-nov-font-setup))

(use-package
 doom-modeline
 :ensure t
 :init (doom-modeline-mode 1))

(use-package transmission :defer t :custom (transmission-host "192.168.0.108"))

;; insert mode for vc-log-edit
(evil-set-initial-state 'log-edit-mode 'insert)

(defun my/vc-dir-refresh-on-window-change (window)
  "Automatically refresh `vc-dir` when its window becomes active."
  (when (eq major-mode 'vc-dir-mode)
    (vc-dir-refresh)))

(add-hook 'window-selection-change-functions #'my/vc-dir-refresh-on-window-change)

(setq user-mail-address "ourgal@qq.com")
(setq user-full-name "ourgal")
(setq message-send-mail-function 'smtpmail-send-it)

(setq
 smtpmail-smtp-user "ourgal@qq.com"
 smtpmail-smtp-server "smtp.qq.com"
 smtpmail-smtp-service 465
 smtpmail-stream-type 'ssl)

(setq smtpmail-debug-info t)
(setq smtpmail-debug-verb t)

(add-to-list 'auth-sources (expand-file-name ".authinfo" user-emacs-directory))
(setq gnus-select-method '(nnnil nil))
(setq gnus-secondary-select-methods
      '((nnimap
         "qq"
         (nnimap-address "imap.qq.com")
         (nnimap-index "nnimap+qq:INDEX")
         (nnmail-expiry-target "nnimap+qq:Deleted Messages")
         (nnimap-expunge t)
         (nnimap-server-port 993)
         (nnimap-stream ssl))
        (nnimap
         "163"
         (nnimap-address "imap.163.com")
         (nnimap-index "nnimap+163:INDEX")
         (nnmail-expiry-target "nnimap+163:已删除")
         (nnimap-expunge t)
         (nnimap-server-port 993)
         (nnimap-stream ssl))
        (nnimap
         "yandex"
         (nnimap-address "imap.yandex.com")
         (nnimap-index "nnimap+yandex:INDEX")
         (nnmail-expiry-target "nnimap+yandex:Trash")
         (nnimap-expunge t)
         (nnimap-server-port 993)
         (nnimap-stream ssl))))

(setq gnus-thread-sort-functions
      '(gnus-thread-sort-by-number (not gnus-thread-sort-by-date)))

(with-eval-after-load 'gnus-sum
  ;; Set font family and size for read messages in the summary
  (set-face-attribute 'gnus-summary-normal-read nil
                      :family "Maple Mono NF CN"
                      :height 120
                      :weight 'normal)

  ;; Set font family and size for unread messages in the summary
  (set-face-attribute 'gnus-summary-normal-unread nil
                      :family "Maple Mono NF CN"
                      :height 120
                      :weight 'bold))

(use-package
 flycheck
 :ensure t
 :hook
 ((after-init . global-flycheck-mode)
  ;; Show diagnostics inline, next to the code (Error Lens style)
  (after-init . global-flycheck-annotate-mode))
 :config
 ;; Report Eglot's LSP diagnostics through Flycheck
 (global-flycheck-eglot-mode 1))

(use-package elfeed
  :ensure t
  :bind ("C-x E" . elfeed)
  :config
  (setq elfeed-db-directory "~/.emacs.d/elfeeddb/")
  (setq elfeed-search-filter "@2-weeks-ago +unread")) ; Default search filter

(use-package elfeed-org
  :ensure t
  :after elfeed
  :config
  (elfeed-org)
  ;; Define the location of your Org file containing the feeds
  (setq rmh-elfeed-org-files '("~/org/elfeed.org")))
