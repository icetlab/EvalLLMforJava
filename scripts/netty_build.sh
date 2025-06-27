#!/bin/bash

BUILD_SUBMODULE=$1

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

./mvnw -pl "${BUILD_SUBMODULE}" -am install -DskipTests -Dcheckstyle.skip=true
