# crm-sync-lambda

AWS Lambda consumer that listens to Kafka events via the **Confluent Cloud AWS Lambda Sink Connector** and upserts onboarded users into Salesforce as Contacts.

## Dependencies (to add to `requirements.txt`)

```
simple-salesforce>=1.12
pydantic>=2
pydantic-settings>=2
```

`PyJWT[crypto]` is pulled transitively by `simple-salesforce`.

The `kafka_events` and `crm` libs are imported from `/libs/` (PYTHONPATH).

## Environment variables (Lambda config)

| Var | Source | Example |
|---|---|---|
| `SF_CONSUMER_KEY` | External Client App Consumer Key | `3MVG9...` |
| `SF_USERNAME` | Integration user's SF username | `integration@azref.ma.dev` |
| `SF_PRIVATE_KEY` | RSA private key (PEM) — from Secrets Manager | `-----BEGIN RSA PRIVATE KEY-----\n...` |
| `SF_DOMAIN` | `login` (prod/dev) or `test` (sandbox) | `login` |
| `SF_EXTERNAL_ID_FIELD` | optional, defaults to `External_User_Id__c` | |

## Local testing

```bash
cd services/crm-sync-lambda
python -m pytest -v
```

The 7 unit tests stub the CRM client so they run **without** `simple-salesforce` installed.

## Packaging for AWS Lambda

```bash
cd services/crm-sync-lambda
rm -rf build && mkdir build
cp -r app build/
cp -r ../../libs/crm build/
cp -r ../../libs/kafka_events build/
pip install -r requirements.txt -t build/
cd build && zip -r ../crm-sync-lambda.zip . && cd ..
```

Then upload `crm-sync-lambda.zip` via AWS Lambda console.

**Handler entry point** (Lambda config): `app.handler.lambda_handler`

**Runtime**: Python 3.13

**Memory**: 256 MB is plenty (~50 MB resident).

**Timeout**: 30s is generous (single SF upsert ~200-400ms).

## Connecting to Confluent

In Confluent Cloud → Connectors → AWS Lambda Sink:

- Topic: `azref.user.events`
- Lambda function ARN: `arn:aws:lambda:...:function:crm-sync-lambda`
- Auth: IAM role with `lambda:InvokeFunction`
- Batch size: leave default
- Behavior on error: log + continue (the handler already swallows per-record errors)
