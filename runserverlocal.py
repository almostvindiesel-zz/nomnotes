import os
os.environ['NOMNOMTES_ENVIRONMENT'] = 'local'

from nomnotes import app

if __name__ == '__main__':
    app.run(host='0.0.0.0')


#app.config.from_envvar('NOMNOTES_SETTINGS', silent=True)

#import views