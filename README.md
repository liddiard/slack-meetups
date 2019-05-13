# meetups

## Stack

- Django running on Python 3
- SQLite database
- Slack Python SDK

## Deployment instructions

1. configure `app.yaml` at root of repo (see example below)
2. run `SECRET_KEY='development' python manage.py collectstatic`
3. run `gcloud app deploy`


`./cloud_sql_proxy -instances="slack-meetups-01=tcp:3306'`

### Example YAML config:

```yaml
runtime: python37

env_variables:
  SECRET_KEY: "[SECRET_KEY]"
  SLACK_API_TOKEN: "[SLACK_API_TOKEN]"
  SLACK_SIGNING_SECRET: "[SLACK_SIGNING_SECRET]"
  DB_PASSWORD: "[DB_PASSWORD]"

handlers: 
- url: /static
  static_dir: static/
- url: /.*
  secure: always
  redirect_http_response_code: 301
  script: auto
```

## TODO

### MVP

- validate that incoming Slack requests are sent from the actual person: https://api.slack.com/docs/verifying-requests-from-slack
- more comprehensive validation of API input

### Post-MVP

- automatic reporting of stats
- analytics graphs
- can we determine when a person joined Slack and use that info somehow?
- unit tests? maybe? 😬
