from argostranslate import package, translate

#Atualiza o índice de pacotes disponíveis
package.update_package_index()
available = package.get_available_packages()

def install_lang(from_code: str, to_code: str):
    pkg = next(
        p for p in available
        if p.from_code == from_code and p.to_code == to_code
    )
    download_path = pkg.download() #baixa o .argosmodel
    package.install_from_path(download_path)

install_lang("en", "pt") #Inglês -> Português
install_lang("pt", "en") #Portguês -> Inglês
install_lang("fr", "en") #Francês -> Inglês
install_lang("en", "fr") #Inglês -> Francês

print(translate.translate("hello world", "en", "fr"))
