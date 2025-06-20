package jadx.gui.ui.dialog;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Set;

import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;

import jadx.gui.ui.MainWindow;
import jadx.gui.ui.filedialog.FileDialogWrapper;
import jadx.gui.ui.filedialog.FileOpenMode;
import jadx.gui.utils.NLS;
import jadx.zip.ZipReader;

public class ApkDiffDialog extends CommonDialog {
    private static final long serialVersionUID = -1L;

    private JTextField oldField;
    private JTextField newField;
    private JTextArea resultArea;

    public ApkDiffDialog(MainWindow mainWindow) {
        super(mainWindow);
        initUI();
    }

    private void compare() {
        Path oldPath = Path.of(oldField.getText());
        Path newPath = Path.of(newField.getText());
        resultArea.setText("");
        try {
            Map<String, String> oldMap = buildHashMap(oldPath);
            Map<String, String> newMap = buildHashMap(newPath);
            Set<String> names = new HashSet<>();
            names.addAll(oldMap.keySet());
            names.addAll(newMap.keySet());
            StringBuilder sb = new StringBuilder();
            for (String name : names) {
                String o = oldMap.get(name);
                String n = newMap.get(name);
                if (o == null) {
                    sb.append("ADDED ").append(name).append('\n');
                } else if (n == null) {
                    sb.append("REMOVED ").append(name).append('\n');
                } else if (!o.equals(n)) {
                    sb.append("CHANGED ").append(name).append('\n');
                }
            }
            resultArea.setText(sb.toString());
        } catch (Exception e) {
            resultArea.setText("Error: " + e.getMessage());
        }
    }

    private Map<String, String> buildHashMap(Path apk) throws Exception {
        Map<String, String> map = new HashMap<>();
        ZipReader reader = new ZipReader();
        reader.readEntries(apk.toFile(), (entry, in) -> {
            try {
                map.put(entry.getName(), md5(in.readAllBytes()));
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });
        return map;
    }

    private static String md5(byte[] data) throws Exception {
        java.security.MessageDigest digest = java.security.MessageDigest.getInstance("MD5");
        digest.update(data);
        byte[] arr = digest.digest();
        StringBuilder sb = new StringBuilder(arr.length * 2);
        for (byte b : arr) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    private JButton makeBrowseButton(JTextField field) {
        JButton button = new JButton("...");
        button.addActionListener(e -> {
            FileDialogWrapper fd = new FileDialogWrapper(mainWindow, FileOpenMode.CUSTOM_OPEN);
            List<Path> files = fd.show();
            if (!files.isEmpty()) {
                field.setText(files.get(0).toString());
            }
        });
        return button;
    }

    private JPanel makeFileRow(String label, JTextField field) {
        JLabel lbl = new JLabel(label);
        JPanel row = new JPanel();
        row.setLayout(new BoxLayout(row, BoxLayout.LINE_AXIS));
        row.add(lbl);
        row.add(Box.createRigidArea(new Dimension(5, 0)));
        row.add(field);
        row.add(Box.createRigidArea(new Dimension(5, 0)));
        row.add(makeBrowseButton(field));
        return row;
    }

    private void initUI() {
        oldField = new JTextField(30);
        newField = new JTextField(30);
        resultArea = new JTextArea();
        resultArea.setEditable(false);

        JPanel fields = new JPanel();
        fields.setLayout(new BoxLayout(fields, BoxLayout.PAGE_AXIS));
        fields.add(makeFileRow(NLS.str("diff_dialog.old_apk"), oldField));
        fields.add(Box.createRigidArea(new Dimension(0, 5)));
        fields.add(makeFileRow(NLS.str("diff_dialog.new_apk"), newField));
        fields.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));

        JButton compareBtn = new JButton(NLS.str("diff_dialog.compare"));
        compareBtn.addActionListener(e -> compare());

        JPanel buttons = new JPanel();
        buttons.setLayout(new BoxLayout(buttons, BoxLayout.LINE_AXIS));
        buttons.add(Box.createHorizontalGlue());
        buttons.add(compareBtn);
        buttons.add(Box.createRigidArea(new Dimension(10, 0)));
        JButton closeBtn = new JButton(NLS.str("common_dialog.close"));
        closeBtn.addActionListener(e -> dispose());
        buttons.add(closeBtn);
        buttons.setBorder(BorderFactory.createEmptyBorder(0, 10, 10, 10));

        JScrollPane scroll = new JScrollPane(resultArea);
        scroll.setPreferredSize(new Dimension(500, 300));

        getContentPane().add(fields, BorderLayout.PAGE_START);
        getContentPane().add(scroll, BorderLayout.CENTER);
        getContentPane().add(buttons, BorderLayout.PAGE_END);

        setTitle(NLS.str("diff_dialog.title"));
        commonWindowInit();
    }
}
