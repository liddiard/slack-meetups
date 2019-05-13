from meetups.wsgi import application
# App Engine by default looks for a main.py file at the root of the app
# directory with a WSGI-compatible object called app.
app = application
