;;; $DOOMDIR/config.el -*- lexical-binding: t; -*-

;; Place your private configuration here! Remember, you do not need to run 'doom
;; sync' after modifying this file!


;; Some functionality uses this to identify you, e.g. GPG configuration, email
;; clients, file templates and snippets. It is optional.
;; (setq user-full-name "John Doe"
;;       user-mail-address "john@doe.com")

;; Doom exposes five (optional) variables for controlling fonts in Doom:
;;
;; - `doom-font' -- the primary font to use
;; - `doom-variable-pitch-font' -- a non-monospace font (where applicable)
;; - `doom-big-font' -- used for `doom-big-font-mode'; use this for
;;   presentations or streaming.
;; - `doom-symbol-font' -- for symbols
;; - `doom-serif-font' -- for the `fixed-pitch-serif' face
;;
;; See 'C-h v doom-font' for documentation and more examples of what they
;; accept. For example:
;;
;; If you or Emacs can't find your font, use 'M-x describe-font' to look them
;; up, `M-x eval-region' to execute elisp code, and 'M-x doom/reload-font' to
;; refresh your font settings. If Emacs still can't find your font, it likely
;; wasn't installed correctly. Font issues are rarely Doom issues!

;; Whenever you reconfigure a package, make sure to wrap your config in an
;; `with-eval-after-load' block, otherwise Doom's defaults may override your
;; settings. E.g.
;;
;;   (with-eval-after-load 'PACKAGE
;;     (setq x y))
;;
;; The exceptions to this rule:
;;
;;   - Setting file/directory variables (like `org-directory')
;;   - Setting variables which explicitly tell you to set them before their
;;     package is loaded (see 'C-h v VARIABLE' to look them up).
;;   - Setting doom variables (which start with 'doom-' or '+').
;;
;; Here are some additional functions/macros that will help you configure Doom.
;;
;; - `load!' for loading external *.el files relative to this one
;; - `add-load-path!' for adding directories to the `load-path', relative to
;;   this file. Emacs searches the `load-path' when you load packages with
;;   `require' or `use-package'.
;; - `map!' for binding new keys
;;
;; To get information about any of these functions/macros, move the cursor over
;; the highlighted symbol at press 'K' (non-evil users must press 'C-c c k').
;; This will open documentation for it, including demos of how they are used.
;; Alternatively, use `C-h o' to look up a symbol (functions, variables, faces,
;; etc).
;;
;; You can also try 'gd' (or 'C-c c d') to jump to their definition and see how
;; they are implemented.

(setq package-archives '( ("gnu"    . "https://mirror.nju.edu.cn/elpa/gnu/")
                          ("nongnu" . "https://mirror.nju.edu.cn/elpa/nongnu/")
                          ("melpa"  . "https://mirror.nju.edu.cn/elpa/melpa/")))

;; There are two ways to load a theme. Both assume the theme is installed and
;; available. You can either set `doom-theme' or manually load a theme with the
;; `load-theme' function. This is the default:
(setq doom-theme 'doom-tokyo-night)

(setq display-line-numbers-type 'relative)

(setq user-full-name "zxc")

(let ((font (if (eq system-type 'android) "IosevkaTerm Nerd Font" "IosevkaTerm NFM"))
      (size (if (eq system-type 'android) 30 15)))
    (setq doom-font (font-spec :family font :size size)
            doom-variable-pitch-font (font-spec :family font :size size)))

(setq doom-themes-enable-bold t
      doom-themes-enable-italic t)

(+global-word-wrap-mode)

(global-visual-line-mode)

(when (not (eq system-type 'windows-nt))
    (add-hook! 'after-save-hook #'executable-make-buffer-file-executable-if-script-p))

(add-hook! 'completion-at-point-functions #'cape-dabbrev)
(add-hook! 'completion-at-point-functions #'cape-file)

(after! doom-modeline
  (setq doom-modeline-buffer-file-name-style 'relative-to-project))

(setq org-directory "~/org/")

(setq org-agenda-files '("~/org/agenda.org"))

(use-package! org-auto-tangle
  :hook org-mode
  :custom
  (org-auto-tangle-default t))

(setq emms-source-file-default-directory "~/Music")
(add-hook 'emms-playlist-mode-hook #'turn-on-evil-mode)

(when (eq system-type 'android)
    (setq overriding-text-conversion-style nil))

;; (map! :n "C-w o" #'delete-other-windows
;;       :n "C-w z" #'doom/window-enlargen)

;; (map! :map Info-mode-map
;;       "C-c C-c" #'gt-translate)
;; (map! :map eww-mode-map
;;       "C-c C-c" #'gt-translate)

(map! :n "RET" #'evil-ex)

(use-package! ahk-mode
  :mode "\\.ahk\\'")

(set-formatter! 'prettier-markdown '("prettier" "--parser" "markdown") :modes '(markdown-mode))
(set-formatter! 'shfmt '("shfmt") :modes '(sh-mode))
(set-formatter! 'ruff '("ruff" "format" "-") :modes '(python-mode))
(set-formatter! 'fnlfmt '("fnlfmt" "-") :modes '(fennel-mode))
(set-formatter! 'nixfmt '("nixfmt" "--strict" "-") :modes '(nix-mode))
(set-formatter! 'taplo '("taplo" "fmt" "-") :modes '(conf-toml-mode))
(set-formatter! 'yamlfix '("yamlfix" "-") :modes '(yaml-mode))

(after! dirvish
  (dirvish-side-follow-mode))

(map! :n "-" #'dirvish)
(map! :map 'dirvish-mode-map :n "a" #'dired-create-empty-file)

(after! eglot
  (add-to-list 'eglot-server-programs
               '(fennel-mode . ("fennel-ls")))
  (add-hook 'fennel-mode-hook 'eglot-ensure)
  (add-to-list 'eglot-server-programs
               '(fish-mode . ("fish-lsp" "start")))
  (add-hook 'fish-mode-hook 'eglot-ensure)
  (add-to-list 'eglot-server-programs
               '(just-mode . ("just-lsp")))
  (add-hook 'just-mode-hook 'eglot-ensure)
  (add-to-list 'eglot-server-programs
               '(just-ts-mode . ("just-lsp")))
  (add-hook 'just-ts-mode-hook 'eglot-ensure)
  (add-to-list 'eglot-server-programs
               '(makefile-gmake-mode . ("make-language-server")))
  (add-hook 'makefile-gmake-mode-hook 'eglot-ensure))

(setq lua-lsp-dir (expand-file-name "~/.local/share/lua-language-server/"))

(setq rmh-elfeed-org-files (list "~/org/elfeed.org"))
(setq elfeed-search-filter "@2-weeks-ago +unread ")

(setq user-mail-address "ourgal@qq.com")
(setq user-full-name "ourgal")
(setq message-send-mail-function 'smtpmail-send-it)

(setq smtpmail-smtp-user "ourgal@qq.com"
      smtpmail-smtp-server "smtp.qq.com"
      smtpmail-smtp-service 465
      smtpmail-stream-type 'ssl)

(setq smtpmail-debug-info t)
(setq smtpmail-debug-verb t)

(setq auth-sources (expand-file-name "~/.config/doom/.authinfo"))
(setq gnus-select-method '(nnnil nil))
(setq gnus-secondary-select-methods
      '( (nnimap "qq"
                 (nnimap-address "imap.qq.com")
                 (nnimap-index "nnimap+qq:INDEX")
                 (nnmail-expiry-target "nnimap+qq:Deleted Messages")
                 (nnimap-expunge t)
                 (nnimap-server-port 993)
                 (nnimap-stream ssl))
         (nnimap "163"
                 (nnimap-address "imap.163.com")
                 (nnimap-index "nnimap+163:INDEX")
                 (nnmail-expiry-target "nnimap+163:已删除")
                 (nnimap-expunge t)
                 (nnimap-server-port 993)
                 (nnimap-stream ssl))
         (nnimap "yandex"
                 (nnimap-address "imap.yandex.com")
                 (nnimap-index "nnimap+yandex:INDEX")
                 (nnmail-expiry-target "nnimap+yandex:Trash")
                 (nnimap-expunge t)
                 (nnimap-server-port 993)
                 (nnimap-stream ssl))))

(setq gnus-thread-sort-functions '(gnus-thread-sort-by-number (not gnus-thread-sort-by-date)))

(use-package! evil
  :defer t
  :custom
  (evil-cross-lines t)
  (evil-ex-search-persistent-highlight nil)
  (+evil-want-o/O-to-continue-comments nil)
  (evil-ex-substitute-global t))

(use-package! nov
  :mode "\\.epub\\'")

(use-package! pangu-spacing
  :hook markdown-mode)

(require 'url)
(require 'json)

(defun insert-github-package-snippet ()
  "从系统剪贴板读取 GitHub 仓库 URL，
抓取它的 repo 名和 description，在光标处插入类似：
[\"repo\", \"desc\", \"https://…\", Categories.SYSTEM, \"MM/DD/YYYY\", None, Waiting_Status.WAITING, Types.PACKAGE],"
  (interactive)
  ;; 1. 取剪贴板内容
  (let* ( (clip (if (fboundp 'gui-get-selection)
                    (gui-get-selection 'CLIPBOARD)
                  (current-kill 0)))
          (url  (and clip (string-trim clip)))
          ;; 2. 提取 repo 全路径 user/repo 及 repo 名
          (m    (and url (string-match "github\\.com/\\([^/]+/[^/]+\\)" url)))
          (full (and m (match-string 1 url)))
          (repo (and full (file-name-nondirectory full))))
    (unless (and url full repo)
      (user-error "剪贴板中没有有效的 GitHub 仓库 URL"))
    ;; 3. 通过 GitHub API 拉 description
    (let* ( (api    (format "https://api.github.com/repos/%s" full))
            ;; 设置一个简单的 User-Agent 以防被拒
            (url-request-extra-headers
             '(("User-Agent" . "emacs-insert-github-package-snippet")))
            (buf    (url-retrieve-synchronously api))
            description)
      (unless buf (user-error "无法访问 GitHub API"))
      (with-current-buffer buf
        (goto-char (point-min))
        (re-search-forward "^$" nil 'move)  ; 跳过 header
        (let ( (json-object-type 'alist)
               (json (json-read)))
          (setq description (or (alist-get 'description json) ""))))
      (kill-buffer buf)
      ;; 4. 插入结果
      (insert
       (format "[\"%s\", \"%s\", \"%s\", Categories.SYSTEM, \"%s\", None, Waiting_Status.WAITING, Types.PACKAGE],"
               repo
               ;; 转义双引号
               (replace-regexp-in-string "\"" "\\\\\"" description)
               url
               ;; 用今天的日期
               (format-time-string "%m/%d/%Y"))))))
