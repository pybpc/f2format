#!/usr/bin/env bash

(
    cd vendor/cpython
    git checkout master
    git reset --hard
    git pull
)

for version in "36" "37" ; do
    case ${version} in
        36) (
                cd vendor/cpython
                git checkout 3.6
                git reset --hard
                git pull
            ) ;;
        37) (
                cd vendor/cpython
                git checkout 3.7
                git reset --hard
                git pull
            ) ;;
    esac

    for path in "Grammar" "Include" "Parser" "Python" ; do
        for file in $( ls vendor/typed_ast/ast3/${path}/ ) ; do
            echo ${file}
            cp vendor/cpython/${path}/${file} src/py${version}/ast/${path}/${file}
        done
    done

    for file in $( ls vendor/typed_ast/ast3/Pgen/ ) ; do
        cp vendor/typed_ast/ast3/Pgen/${file} src/py${version}/ast/Pgen/${file}
    done

    cp vendor/typed_ast/ast3/compile_pgen src/py${version}/ast/compile_pgen
done

(
    cd vendor/cpython
    git checkout master
    git reset --hard
    git pull
)
