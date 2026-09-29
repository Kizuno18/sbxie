#include <QtWidgets>
#include <cstdio>
#include "fake_sbie_ini.h"
#include "SharedAccessWidget.h"

static int failures = 0;
static void check(bool passed, const char* message)
{
    if (!passed) {
        std::printf("FAIL: %s\n", message);
        ++failures;
    }
}

int main(int argc, char* argv[])
{
    QApplication app(argc, argv);
    auto ini = QSharedPointer<CSbieIni>::create();
    ini->values["ClosedFilePath"] = {"<Restricted>,C:\\private", "!<Excluded>,C:\\other"};
    ini->values["ReadFilePathDisabled"] = {"reader.exe,C:\\readonly"};
    const auto original = ini->values;
    CSharedFileWidget widget;
    widget.SetConfig(ini, false);
    widget.LoadAccessList();
    widget.SaveAccessList();
    for (auto it = original.cbegin(); it != original.cend(); ++it) {
        auto expected = it.value();
        auto actual = ini->values.value(it.key());
        expected.sort();
        actual.sort();
        check(actual == expected, "Group/program or disabled rule changed during round trip");
    }

    ini->templates["Template_Test"]["OpenFilePath"] = {"C:\\template"};
    widget.SetShowTemplates(true);
    check(widget.GetItemCount() == 4, "Template rows duplicated");
    widget.SaveAccessList();
    check(ini->values["OpenFilePath"].isEmpty(), "Template rule was copied into sandbox settings");
    widget.SetShowTemplates(false);
    check(widget.GetItemCount() == 3, "Template rows not removed");

    for (const QString key : {QString("ClosedFilePath"), QString("ClosedFilePathDisabled")}) {
        ini->failKey = key;
        bool reported = false;
        try { widget.SaveAccessList(); }
        catch (const SB_STATUS& status) { reported = !status.success; }
        check(reported, "INI save failure was swallowed");
    }
    ini->failKey.clear();

    auto item = widget.GetTree()->topLevelItem(0);
    check(QMetaObject::invokeMethod(&widget, "OnItemDoubleClicked", Qt::DirectConnection,
        Q_ARG(QTreeWidgetItem*, item), Q_ARG(int, 3)), "Cannot enter access editor");
    auto editor = qobject_cast<QLineEdit*>(widget.GetTree()->itemWidget(item, 3));
    check(editor != nullptr, "Path editor missing");
    if (editor) {
        editor->setText("C:\\edited");
        widget.CloseAccessEdit(true);
        check(item->data(3, Qt::UserRole).toString() == "C:\\edited", "Pending edit lost");
    }
    return failures ? 1 : 0;
}
