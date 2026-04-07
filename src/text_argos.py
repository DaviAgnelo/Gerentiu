import argostranslate.package

argostranslate.package.update_package_index()
packages = argostranslate.package.get_available_packages()

wanted = {
    ("en", "pt"), ("pt", "en"),
    ("en", "es"), ("es", "en"),
    ("en", "fr"), ("fr", "en"),
    ("en", "de"), ("de", "en"),
    ("en", "it"), ("it", "en"),
    ("en", "ru"), ("ru", "en"),
    ("en", "ja"), ("ja", "en"),
    ("en", "zh"), ("zh", "en"),
    ("en", "hi"), ("hi", "en"),
    ("en", "ko"), ("ko", "en"),
}

for p in packages:
    if (p.from_code, p.to_code) in wanted:
        print(f"Installing {p.from_code}->{p.to_code}")
        path = p.download()
        argostranslate.package.install_from_path(path)

print("DONE 🔥")
