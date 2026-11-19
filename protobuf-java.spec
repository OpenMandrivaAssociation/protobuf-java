%global _disable_lto 1
%global proto_ver 36.2
%global old_proto 33.2

Name:		protobuf-java
Version:	4.36.2
Release:	1
Summary:	Java Protocol Buffers runtime
Group:		Development/Java
License:	BSD-3-Clause
URL:		https://protobuf.dev/
Source0:	https://github.com/protocolbuffers/protobuf/archive/refs/tags/v%{proto_ver}.tar.gz#/protobuf-%{proto_ver}.tar.gz
Source1:	https://github.com/abseil/abseil-cpp/archive/refs/tags/20250512.1.tar.gz#/abseil-cpp-20250512.1.tar.gz
Source2:	https://github.com/protocolbuffers/protobuf/archive/refs/tags/v%{old_proto}.tar.gz#/protobuf-%{old_proto}.tar.gz

BuildArch:	noarch
BuildRequires:	java-current-devel
BuildRequires:	sysjar
BuildRequires:	cmake
BuildRequires:	ninja
BuildRequires:	clang

%description
Protocol Buffers serialize structured data. This package is the Java
runtime com.google.protobuf:protobuf-java %{version}. Well-known types
are generated with protoc %{proto_ver} built from the same source tag.
That compiler, and the abseil 20250512.1 sources it links, are not
installed. The 4.33.2 jar stays installed because error-prone requires
mvn(com.google.protobuf:protobuf-java) = 4.33.2. The %{version} sources
drop the internal BinaryReader, BinaryWriter, and SchemaFull classes
and add InternalLazyField.

%prep
%autosetup -n protobuf-%{proto_ver} -a 1 -p1
find . \( -name '*.jar' -o -name '*.class' -o -name '*.so' -o -name '*.node' -o -name '*.wasm' \) -delete
tar -C %{_builddir} -xf %{SOURCE2}
find "%{_builddir}/protobuf-%{old_proto}" \( -name '*.jar' -o -name '*.class' -o -name '*.so' -o -name '*.node' -o -name '*.wasm' \) -delete

%build
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH="$JAVA_HOME/bin:$PATH"

# lld drops upb start/stop section symbols unless nostart-stop-gc is set.
cmake -S abseil-cpp-20250512.1 -B absl-build -G Ninja \
	-DCMAKE_BUILD_TYPE=Release \
	-DCMAKE_INSTALL_PREFIX="$PWD/absl-prefix" \
	-DCMAKE_EXE_LINKER_FLAGS="-Wl,-z,nostart-stop-gc" \
	-DABSL_BUILD_TESTING=OFF \
	-DABSL_ENABLE_INSTALL=ON \
	-DABSL_PROPAGATE_CXX_STD=ON \
	-DBUILD_SHARED_LIBS=OFF
cmake --build absl-build -j"$(nproc)"
cmake --install absl-build

ABSL="$PWD/absl-prefix"
test -d "$ABSL"
compile_tree() (
	set -eo pipefail
	dir=$1
	pver=$2
	rver=$3
	core_n=$4
	cd "$dir"
	cmake -S . -B proto-build -G Ninja \
		-DCMAKE_BUILD_TYPE=Release \
		-DCMAKE_PREFIX_PATH="$ABSL" \
		-DCMAKE_EXE_LINKER_FLAGS="-Wl,-z,nostart-stop-gc" \
		-Dprotobuf_BUILD_TESTS=OFF \
		-Dprotobuf_BUILD_CONFORMANCE=OFF \
		-Dprotobuf_BUILD_EXAMPLES=OFF \
		-Dprotobuf_LOCAL_DEPENDENCIES_ONLY=ON \
		-Dprotobuf_INSTALL=OFF \
		-Dprotobuf_WITH_ZLIB=OFF \
		-DBUILD_SHARED_LIBS=OFF
	cmake --build proto-build --target protoc -j"$(nproc)"
	./proto-build/protoc --version | grep -F -q "libprotoc ${pver}"

	mkdir -p generated
	./proto-build/protoc --java_out=generated \
		--proto_path=src \
		--proto_path=java/core/src/main/resources \
		java/core/src/main/resources/google/protobuf/java_features.proto \
		src/google/protobuf/any.proto \
		src/google/protobuf/api.proto \
		src/google/protobuf/descriptor.proto \
		src/google/protobuf/duration.proto \
		src/google/protobuf/empty.proto \
		src/google/protobuf/field_mask.proto \
		src/google/protobuf/source_context.proto \
		src/google/protobuf/struct.proto \
		src/google/protobuf/timestamp.proto \
		src/google/protobuf/type.proto \
		src/google/protobuf/wrappers.proto \
		src/google/protobuf/compiler/plugin.proto

	# --release 8 hides sun.misc. A compile-only stub keeps major version 52.
	mkdir -p unsafe-stub/src/sun/misc
	cat > unsafe-stub/src/sun/misc/Unsafe.java << 'EOF'
package sun.misc;
import java.lang.reflect.Field;
public class Unsafe {
	public Object allocateInstance(Class<?> cls) throws InstantiationException { return null; }
	public long objectFieldOffset(Field f) { return 0; }
	public long staticFieldOffset(Field f) { return 0; }
	public Object staticFieldBase(Field f) { return null; }
	public int arrayBaseOffset(Class<?> c) { return 0; }
	public int arrayIndexScale(Class<?> c) { return 0; }
	public int getInt(Object o, long off) { return 0; }
	public void putInt(Object o, long off, int v) {}
	public long getLong(Object o, long off) { return 0; }
	public void putLong(Object o, long off, long v) {}
	public Object getObject(Object o, long off) { return null; }
	public void putObject(Object o, long off, Object v) {}
	public boolean getBoolean(Object o, long off) { return false; }
	public void putBoolean(Object o, long off, boolean v) {}
	public byte getByte(Object o, long off) { return 0; }
	public void putByte(Object o, long off, byte v) {}
	public float getFloat(Object o, long off) { return 0; }
	public void putFloat(Object o, long off, float v) {}
	public double getDouble(Object o, long off) { return 0; }
	public void putDouble(Object o, long off, double v) {}
	public byte getByte(long a) { return 0; }
	public void putByte(long a, byte v) {}
	public int getInt(long a) { return 0; }
	public void putInt(long a, int v) {}
	public long getLong(long a) { return 0; }
	public void putLong(long a, long v) {}
	public void copyMemory(Object s, long so, Object d, long dOff, long n) {}
}
EOF
	javac --release 8 -encoding UTF-8 -Xlint:-options -proc:none -d unsafe-stub unsafe-stub/src/sun/misc/Unsafe.java
	jar cf unsafe-stub.jar -C unsafe-stub sun

	find java/core/src/main/java -name '*.java' ! -name 'module-info.java' > sources.list
	find generated -name '*.java' ! -name 'module-info.java' >> sources.list
	test "$(grep -c 'java/core/src/main/java/' sources.list)" -eq "$core_n"
	test "$(grep -c '^generated/' sources.list)" -eq 67

	mkdir -p classes
	javac --release 8 -encoding UTF-8 -Xlint:-options -proc:none -cp unsafe-stub.jar -d classes @sources.list

	mkdir -p classes/google/protobuf
	for proto in any api descriptor duration empty field_mask source_context struct timestamp type wrappers; do
		cp -p "src/google/protobuf/${proto}.proto" classes/google/protobuf/
	done
	cp -p java/core/src/main/resources/google/protobuf/java_features.proto classes/google/protobuf/

	jar cf protobuf-java.jar -C classes .
	jar i protobuf-java.jar
	jar tf protobuf-java.jar | grep -E '\.(java|jar|so|node|wasm)$|sun/misc/Unsafe\.class' && exit 1 || true
	jar tf protobuf-java.jar | grep -F -q 'google/protobuf/descriptor.proto'
	jar tf protobuf-java.jar | grep -F -q 'google/protobuf/java_features.proto'
	javap -verbose -cp protobuf-java.jar com.google.protobuf.Duration | grep -F -q 'major version: 52'
	if jar tf protobuf-java.jar | grep -F -q 'com/google/protobuf/BinaryWriter.class'; then
		old_writer=1
	else
		old_writer=0
	fi
	if jar tf protobuf-java.jar | grep -F -q 'com/google/protobuf/InvalidProtobufRuntimeException.class'; then
		new_exc=1
	else
		new_exc=0
	fi
	if [ "$rver" = "%{version}" ]; then
		test "$old_writer" -eq 0
		test "$new_exc" -eq 1
	else
		test "$old_writer" -eq 1
		test "$new_exc" -eq 0
	fi

	cat > protobuf-java.pom << EOF
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.google.protobuf</groupId>
  <artifactId>protobuf-java</artifactId>
  <version>${rver}</version>
  <name>Protocol Buffers [Core]</name>
  <description>Java Protocol Buffers runtime.</description>
  <licenses>
    <license>
      <name>BSD-3-Clause</name>
    </license>
  </licenses>
</project>
EOF
	grep -F -q "<version>${rver}</version>" protobuf-java.pom
)
compile_tree "%{_builddir}/protobuf-%{old_proto}" %{old_proto} 4.33.2 140
compile_tree "%{_builddir}/protobuf-%{proto_ver}" %{proto_ver} %{version} 131

%install
set -eo pipefail
install_one() {
	pomjar=$1
	filename=$2
	list=$3
	sysjar install --buildroot %{buildroot} \
		--artifact "$pomjar" \
		--file-name "$filename" \
		--filelist "$list"
}
old="%{_builddir}/protobuf-%{old_proto}"
install_one "${old}/protobuf-java.pom:${old}/protobuf-java.jar" \
	protobuf-java-4.33.2 .mfiles-old
index="%{buildroot}/usr/share/sysjar/index/com.google.protobuf/protobuf-java.sysjar"
test -f "$index"
/bin/mv "$index" "%{buildroot}/usr/share/sysjar/index/com.google.protobuf/protobuf-java-4.33.2.sysjar"
sed -i 's|/usr/share/sysjar/index/com\.google\.protobuf/protobuf-java\.sysjar|/usr/share/sysjar/index/com.google.protobuf/protobuf-java-4.33.2.sysjar|' .mfiles-old
idx="%{buildroot}/usr/share/sysjar/index/com.google.protobuf/protobuf-java-4.33.2.sysjar"
grep -F -q '"version": "4.33.2"' "$idx"
grep -F -q '"artifactId": "protobuf-java"' "$idx"
test -s "%{buildroot}%{_javadir}/protobuf-java-4.33.2.jar"
new="%{_builddir}/protobuf-%{proto_ver}"
install_one "${new}/protobuf-java.pom:${new}/protobuf-java.jar" \
	protobuf-java .mfiles-new
idxn="%{buildroot}/usr/share/sysjar/index/com.google.protobuf/protobuf-java.sysjar"
grep -F -q '"version": "%{version}"' "$idxn"
grep -F -q '"artifactId": "protobuf-java"' "$idxn"
test -s "%{buildroot}%{_javadir}/protobuf-java.jar"
: > .mfiles
for list in .mfiles-old .mfiles-new
do
	while IFS= read -r line; do
		grep -qxF -- "$line" .mfiles || printf '%%s\n' "$line" >> .mfiles
	done < "$list"
done
grep -F -q '/protobuf-java.jar' .mfiles
grep -F -q '/protobuf-java-4.33.2.jar' .mfiles

%check
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p check
cat > check/Smoke.java << 'END'
import com.google.protobuf.Duration;
public class Smoke {
	public static void main(String[] args) throws Exception {
		Duration d = Duration.newBuilder().setSeconds(3).setNanos(250).build();
		Duration parsed = Duration.parseFrom(d.toByteArray());
		String name = Duration.getDescriptor().getFullName();
		if (parsed.getSeconds() != 3 || parsed.getNanos() != 250) {
			throw new RuntimeException("roundtrip failed");
		}
		if (!"google.protobuf.Duration".equals(name)) {
			throw new RuntimeException(name);
		}
		System.out.println("pb_ok " + parsed.getSeconds() + " " + name);
	}
}
END
run_check() {
	label=$1
	jar=$2
	test -s "$jar"
	mkdir -p "check/${label}"
	javac --release 8 -encoding UTF-8 -Xlint:-options -proc:none -cp "$jar" -d "check/${label}" check/Smoke.java
	java -cp "check/${label}:${jar}" Smoke > "check/${label}/out.txt"
	cat "check/${label}/out.txt"
	grep -F -q 'pb_ok 3 google.protobuf.Duration' "check/${label}/out.txt"
}
run_check new "%{buildroot}%{_javadir}/protobuf-java.jar"
run_check old "%{buildroot}%{_javadir}/protobuf-java-4.33.2.jar"

%files -f .mfiles
%doc LICENSE
