    # workaround for grgit issue
sed -i 's/\(grgit: "\)[0-9.]*"/\14.1.1"/' gradle/dependencies.gradle

# workaround for gradlew wrapper
if [ ! -f "./gradlew" ]; then
    sed -i 's/spotbugsPlugin: *"[0-9.]*"/spotbugsPlugin: "2.0.0"/' gradle/dependencies.gradle
    sed -i -E 's/^\s*(additionalSourceDirs|sourceDirectories|classDirectories|executionData)\s*=\s*files\((.*)\)/\1.setFrom(files(\2))/' build.gradle
    gradle
fi

BUILD_SUBMODULE=$1
./gradlew "${BUILD_SUBMODULE}":build -x test
