# meetups

## Stack

- Django running on Python 3.7+
- SQLite database
- Slack Python SDK

## Deployment instructions

1. create a Google Cloud Postgres instance
2. from the Google Cloud Shell Postgres console, connect to the DB and run `CREATE DATABASE meetups`
3. configure `app.yaml` at root of repo (see example below)
4. run `SECRET_KEY='development' python manage.py collectstatic`
5. download Google Cloud SQL proxy and run it locally (replacing instance name as necesary): `./cloud_sql_proxy -instances="slack-meetups:us-west2:slack-meetups-01=tcp:3306"`
6. while connected to the DB via proxy, run `python manage.py migrate` and `python manage.py createsuperuser`
7. run `gcloud app deploy`

### Example YAML config:

```yaml
runtime: python37

env_variables:
  SECRET_KEY: "[SECRET_KEY]"
  SLACK_API_TOKEN: "[SLACK_API_TOKEN]"
  SLACK_SIGNING_SECRET: "[SLACK_SIGNING_SECRET]"
  DB_HOST: "/cloudsql/slack-meetups:us-west2:slack-meetups-01"
  DB_PASSWORD: "[DB_PASSWORD]"

handlers: 
- url: /static
  static_dir: static/
- url: /.*
  secure: always
  redirect_http_response_code: 301
  script: auto
```

### Useful links

- https://medium.com/@BennettGarner/deploying-a-django-application-to-google-app-engine-f9c91a30bd35
- https://cloud.google.com/sdk/docs/downloads-interactive
- https://cloud.google.com/python/django/appengine
- https://cloud.google.com/appengine/docs/standard/python3/config/appref
- https://cloud.google.com/appengine/docs/standard/python3/runtime#environment_variables
- https://cloud.google.com/sql/docs/postgres/quickstart-proxy-test
- https://cloud.google.com/sql/docs/postgres/connect-admin-ip

## TODO

### MVP

- validate that incoming Slack requests are sent from the actual person: https://api.slack.com/docs/verifying-requests-from-slack
- more comprehensive validation of API input

### Post-MVP

- automatic reporting of stats
- analytics graphs
- can we determine when a person joined Slack and use that info somehow?
- unit tests? maybe? 😬
