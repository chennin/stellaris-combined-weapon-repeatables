# Making

`./make.py`

# Uploading

```
STEAMUSER=
podman run -v $PWD:/code:ro -v steamcmd-root:/root/.local/share/Steam -it index.docker.io/steamcmd/steamcmd:debian-12 \
  +login $STEAMUSER +workshop_build_item /code/steamcmd.txt +quit
```
