Nom notes is an application that helps with travel planning.
Rather than doing your planning from one site, nom notes enables you to 
save notes from the entire web and easily save them to your travel notes,


# ############################################################ INSTALLATION
virtualenv venv
. venv/bin/activate
export PATH=$PATH:/usr/local/mysql/bin
pip install -r requirements.txt
brew install pkg-config libffi
export PKG_CONFIG_PATH=/usr/local/Cellar/libffi/3.0.13/lib/pkgconfig/

export NOMNOTES_SETTINGS=/Users/mars/code/nomnotes/nomnotes/settings.cfg
python runserver.py


