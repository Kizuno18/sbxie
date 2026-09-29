#pragma once
#include <QtCore>

struct SB_STATUS {
    bool success;
    explicit operator bool() const { return success; }
};

class CSbieIni {
public:
    QMap<QString, QStringList> values;
    QMap<QString, QMap<QString, QStringList>> templates;
    QString failKey;
    QStringList GetTextList(const QString& key, bool) const { return values.value(key); }
    QStringList GetTemplates() const { return templates.keys(); }
    QStringList GetTextListTmpl(const QString& key, const QString& name) const {
        return templates.value(name).value(key);
    }
    SB_STATUS UpdateTextList(const QString& key, const QStringList& list, bool) {
        if (key == failKey)
            return {false};
        values[key] = list;
        return {true};
    }
};
