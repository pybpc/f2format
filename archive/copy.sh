#!/usr/bin/env bash

set -x

for version in "36" "37" ; do
    case ${version} in
        36) cd vendor/cpython && \
            git checkout 3.6 && \
            git reset --hard && \
            git clean -fd && \
            git pull
            returncode=$?
            if [[ ${returncode} -ne "0" ]] ; then
                exit ${returncode}
            fi ;;
        37) cd vendor/cpython && \
            git checkout 3.7 && \
            git reset --hard && \
            git clean -fd && \
            git pull
            returncode=$?
            if [[ ${returncode} -ne "0" ]] ; then
                exit ${returncode}
            fi ;;
    esac

    for path in "Include" "Parser" "Python" ; do
        for file in $( ls vendor/typed_ast/ast3/${path}/ ) ; do
            echo "Copying '${file}'..."
            cp vendor/cpython/${path}/${file} src/py${version}/ast/${path}/${file}
        done
    done

    cp vendor/cpython/Lib/ast.py src/py${version}/ast.py
done

cd vendor/cpython && \
git checkout master && \
git reset --hard && \
git clean -fd && \
git pull
returncode=$?
if [[ ${returncode} -ne "0" ]] ; then
    exit ${returncode}
fi
