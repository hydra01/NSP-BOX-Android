[app]
title = NSP Box
package.name = nspbox
package.domain = org.nspbox
source.dir = .
source.include_exts = py,png
source.exclude_dirs = .github,bin,.buildozer,recipes
version = 4.0.1
requirements = python3,kivy==2.3.0,pillow,pyjnius,android,zstandard
icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

android.permissions = MANAGE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,WAKE_LOCK
android.api = 33
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = False

p4a.branch = v2024.01.21
p4a.local_recipes = ./recipes

[buildozer]
log_level = 2
warn_on_root = 1
