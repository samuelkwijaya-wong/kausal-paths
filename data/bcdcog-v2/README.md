# BCDCOG demo model, v2: set up on your own computer

`configs/bcdcog-v2.yaml` is the same model as `configs/bcdcog.yaml`, with the same data
(`data/bcdcog/bcdcog_datasets.csv`). The only difference is where the data is read from: a dataset
repository on your own computer rather than Kausal's shared one. This means you can set it up without
upload credentials. It is only visible on your machine; for a demo others can open, use v1 and the
upload described in `data/bcdcog/README.md`.

## One command

From the kausal-paths folder, with the development environment working (database migrated):

```bash
data/bcdcog-v2/setup_local.sh
```

It does four things:

1. Creates `~/kausal-local-data/bcdcog/`, holding:
   - `datasets.git`: the dataset repository
   - `dvc-storage`: the data files
2. Uploads the CSV into it.
3. Writes that folder and the upload's commit into `configs/bcdcog-v2.yaml`.
4. Computes the model once as a check, and creates the `bcdcog-v2` instance and its pages in the database.

Pass another folder as the first argument to keep the data elsewhere. Then start the server with
`python manage.py runserver`.

## Changing a number

Edit the CSV and run the script again. It re-uploads the data and moves the model to the new commit.

## Before committing

The script rewrites two lines of `configs/bcdcog-v2.yaml` with paths on your computer (`dataset_repo.url`
and `.commit`). Don't commit those; `git checkout configs/bcdcog-v2.yaml` puts the placeholders back.

## Keeping v1 and v2 in step

The two config files are copies apart from their header, `id`, `name` and `dataset_repo`. A change to the
model belongs in both.
