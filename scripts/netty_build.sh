#!/bin/bash

REPO_PATH=$1
cd "$REPO_PATH" || exit 1 # Change to the repository directory

if [ ! -f ./mvnw ]; then
    mvn -N io.takari:maven:wrapper
fi

# Workaround for version issue
find . -name "*.xml" -exec sed -i 's/Final-SNAPSHOT/Final/g' {} \;

# Workaround: skip check-format goal in pom.xml
sed -i '/<goal>check-format<\/goal>/,/<\/goals>/ {
/<\/goals>/ a\
<configuration>\
    <skip>true</skip>\
</configuration>
}' pom.xml

BUILD_SUBMODULE=$2
./mvnw -pl "${BUILD_SUBMODULE}" -am install -DskipTests -Dcheckstyle.skip=true
