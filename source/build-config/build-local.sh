#!/bin/bash
# Swiss build helper (MSYS2 + devkitPPC + libogc2)
# Usage: bash build-local.sh [make target]   e.g. dev | all | clean
# Must run under MSYS2: C:\msys64\usr\bin\bash.exe -lc "bash /d/workbuddy/swiss-gc/build-local.sh dev"

export MSYSTEM=MSYS
export LANG=C.UTF-8
export DEVKITPRO=/opt/devkitpro
export DEVKITPPC=/opt/devkitpro/devkitPPC
export PATH="$DEVKITPPC/bin:$DEVKITPRO/tools/bin:/usr/bin:$PATH"

# buildtools/dol2ipl.py needs Python, but this MSYS2 install has no python3.
# Point Makefile's PYTHON at a Windows Python so `make apploader` / `make all`
# can produce the IGR apploader.img. Override by exporting PYTHON beforehand.
if [ -z "$PYTHON" ]; then
	for p in /c/Users/*/.workbuddy/binaries/python/versions/*/python.exe \
	         /c/Users/*/AppData/Local/Programs/Python/Python3*/python.exe \
	         /c/Python3*/python.exe; do
		if [ -x "$p" ]; then PYTHON="$p"; break; fi
	done
fi
if [ -z "$PYTHON" ] && command -v py >/dev/null 2>&1; then
	PYTHON="$(py -3 -c 'import sys; print(sys.executable)' | tr -d '\r\n')"
	command -v cygpath >/dev/null 2>&1 && PYTHON="$(cygpath -u "$PYTHON")"
fi
export PYTHON="${PYTHON:-python3}"
echo "python:  $PYTHON"

# ASCII-only path is mandatory: gxtexconv crashes on non-ASCII paths
cd /d/workbuddy/swiss-gc || { echo "repo not found"; exit 1; }

TARGET="${1:-dev}"

# "inc" = incremental: only rebuild what changed (much faster for iterating
# on a single source file). The top-level "dev" target always cleans first.
if [ "$TARGET" = "inc" ]; then
	echo "target: incremental (cube/swiss only)"
	cd cube/swiss && exec make
fi

echo "target: $TARGET"
exec make "$TARGET"
