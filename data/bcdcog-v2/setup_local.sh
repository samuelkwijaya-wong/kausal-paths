#!/usr/bin/env bash
# Set up the bcdcog-v2 demo instance on this computer, with its datasets in a local
# DVC repository instead of Kausal's shared one. Needs no credentials.
#
#   data/bcdcog-v2/setup_local.sh [DATA_DIR]
#
# Run from the kausal-paths root, with the database migrated. DATA_DIR (default
# ~/kausal-local-data/bcdcog) receives two folders:
#   datasets.git  -- a bare git repository holding the dataset metadata (.dvc files)
#   dvc-storage   -- the DVC remote: an ordinary folder holding the data files
# Re-running it re-uploads the CSV, so it is also how to apply an edit to the data.
#
# It rewrites `dataset_repo.url` and `dataset_repo.commit` in configs/bcdcog-v2.yaml
# to point at DATA_DIR. Those two lines are specific to this computer.
set -euo pipefail

DATA_DIR="$(mkdir -p "${1:-$HOME/kausal-local-data/bcdcog}" && cd "${1:-$HOME/kausal-local-data/bcdcog}" && pwd)"
GIT_DIR="$DATA_DIR/datasets.git"
STORAGE_DIR="$DATA_DIR/dvc-storage"
CONFIG=configs/bcdcog-v2.yaml
CSV=data/bcdcog/bcdcog_datasets.csv
PYTHON="$(command -v "${PYTHON:-python}")"
# Absolute, because step 1 runs it from another directory.
case "$PYTHON" in /*) ;; *) PYTHON="$PWD/$PYTHON" ;; esac

if [ ! -f "$CONFIG" ]; then
  echo "Run this from the kausal-paths root directory." >&2
  exit 1
fi

# 1. An empty dataset repository, created once.
if [ ! -d "$GIT_DIR" ]; then
  echo "Creating local dataset repository in $DATA_DIR"
  mkdir -p "$STORAGE_DIR"
  git init --quiet --bare --initial-branch=main "$GIT_DIR"
  WORK="$(mktemp -d)"
  git clone --quiet "$GIT_DIR" "$WORK/repo" 2>/dev/null
  (
    cd "$WORK/repo"
    git checkout --quiet -b main
    "$PYTHON" -m dvc init --quiet
    "$PYTHON" -m dvc remote add --default local "$STORAGE_DIR"
    git add .dvc .dvcignore
    git -c user.name="Local datasets" -c user.email="local@localhost" commit --quiet -m "Initialize local DVC repository"
    git push --quiet origin main
  )
  rm -rf "$WORK"
fi

# 2. Point the model at the repository first: loading the model to map the CSV's
#    labels onto its categories (--instance) reads `dataset_repo`.
sed -i.bak -e "s|^  url: .*|  url: $GIT_DIR|" "$CONFIG"
rm -f "$CONFIG.bak"

# 3. Upload the datasets, then pin the model to the commit the upload made.
"$PYTHON" -m tools.upload_new_dataset -i "$CSV" -o bcdcog --instance bcdcog-v2 --language en \
  --repo-url "$GIT_DIR" --dvc-remote local > "$DATA_DIR/upload.log"
echo "Uploaded datasets (log: $DATA_DIR/upload.log)"
COMMIT="$(git --git-dir="$GIT_DIR" rev-parse main)"
sed -i.bak -e "s|^  commit: .*|  commit: $COMMIT|" "$CONFIG"
rm -f "$CONFIG.bak"
echo "Set dataset_repo in $CONFIG to $GIT_DIR @ $COMMIT"

# 4. Compute once as a check, then create (or update) the instance in the database.
"$PYTHON" load_nodes.py -c "$CONFIG" --node net_emissions
"$PYTHON" load_nodes.py -c "$CONFIG" --update-instance --update-nodes
echo "Done. Start the server with: python manage.py runserver"
