#include "../../SandMan/Wizards/PortableBoxIni.h"
#include <QCoreApplication>
#include <QDir>
#include <QTemporaryDir>

static void require(bool passed, const char* message)
{
    if (!passed)
        qFatal("%s", message);
}

int main(int argc, char* argv[])
{
    QCoreApplication app(argc, argv);
    QTemporaryDir directory;
    require(directory.isValid(), "Temporary directory creation failed");
    const QString path = directory.filePath("Portable.ini");
    require(CreatePortableBoxIni(path, "Portable"), "New INI creation failed");
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "Cannot read created INI");
    const QByteArray original = file.readAll();
    file.close();
    require(original.contains("[Portable]\nEnabled=y\n"), "Incorrect INI contents");
    require(!CreatePortableBoxIni(path, "Replacement"), "Existing INI was overwritten");
    require(file.open(QIODevice::ReadOnly), "Original INI disappeared");
    require(file.readAll() == original, "Original INI changed after failure");
    file.close();

    const QString missing = directory.filePath("missing/Box.ini");
    require(!CreatePortableBoxIni(missing, "Box"), "Missing parent unexpectedly succeeded");
    require(!QFile::exists(missing), "Failed creation left an INI behind");
    require(!CreatePortableBoxIni(directory.path(), "Box"), "Directory accepted as INI");
    require(QDir(directory.path()).exists(), "Failed creation removed the directory");
    return 0;
}
