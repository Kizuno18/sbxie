#pragma once

#include <QFile>

inline bool CreatePortableBoxIni(const QString& Path, const QString& BoxName)
{
    const QByteArray content = "#\n"
        "# Portable sandbox configuration file\n"
        "#\n\n[" + BoxName.toLatin1() + "]\nEnabled=y\n";

    QFile file(Path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::NewOnly))
        return false;

    const bool success = file.write(content) == content.size() && file.flush();
    file.close();
    if (!success)
        QFile::remove(Path);
    return success;
}
