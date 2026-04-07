from argostranslate import package, translate

package.update_package_index()
available_packages = package.get_available_packages()

def install_lang(from_code: str, to_code: str):
    pkg = next(
        (p for p in available_packages if p.from_code == from_code and p.to_code == to_code),
        None
    )

    if pkg is None:
        print(f"[!] Pacote não encontrado: {from_code} -> {to_code}")
        return

    print(f"[+] Instalando: {from_code} -> {to_code}")
    download_path = pkg.download()
    package.install_from_path(download_path)

LANGS = ["pt", "en", "fr", "de", "ko", "es", "zh", "ja", "ru", "it", "hi"]

for lang in LANGS:
    if lang != "en":
        install_lang("en", lang)
        install_lang(lang, "en")

print(translate.translate("hello world", "en", "fr"))
