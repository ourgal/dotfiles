;;; post-init.el --- post init -*- no-byte-compile: t; lexical-binding: t; -*-

(require 'org)

(org-babel-load-file (expand-file-name "config.org" user-emacs-directory))
