# Custom SAM build for the mono-repo: we need to bundle libs/crm/ and
# libs/kafka_events/ alongside app/ since they live outside the service
# directory and aren't pip-installable as packages.
#
# SAM calls `build-<LogicalId>` and passes ARTIFACTS_DIR.

.PHONY: build-CrmSyncFunction

build-CrmSyncFunction:
	cp -r app $(ARTIFACTS_DIR)/
	cp -r ../../libs/crm $(ARTIFACTS_DIR)/
	cp -r ../../libs/kafka_events $(ARTIFACTS_DIR)/
	find $(ARTIFACTS_DIR) -type d -name __pycache__ -exec rm -rf {} +
	find $(ARTIFACTS_DIR) -type d -name tests -exec rm -rf {} +
	find $(ARTIFACTS_DIR) -type d -name venv -exec rm -rf {} +
	find $(ARTIFACTS_DIR) -name '*.pyc' -delete
	pip install -r requirements.txt -t $(ARTIFACTS_DIR)/
