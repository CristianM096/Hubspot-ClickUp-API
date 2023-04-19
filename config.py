from configparser import ConfigParser

def config(file='config.ini',section='postgresql'):
    parser = ConfigParser()
    parser.read(file)

    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception('Seccion {0} no encontrada en el archivo {1}'.format(section,file))