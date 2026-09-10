#!/bin/bash
set -e

gcloud run deploy spanish-app \
  --source . \
  --region us-central1
