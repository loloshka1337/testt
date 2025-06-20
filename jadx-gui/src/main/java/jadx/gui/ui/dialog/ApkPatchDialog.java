package jadx.gui.ui.dialog;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;
import java.nio.file.Files;

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

public class ApkPatchDialog extends CommonDialog {
    private static final long serialVersionUID = -1L;

    private JTextField oldField;
    private JTextField oldModField;
    private JTextField newField;
    private JTextField outField;
    private JTextArea resultArea;

    public ApkPatchDialog(MainWindow mainWindow) {
        super(mainWindow);
        initUI();
    }

    private void patch() {
        Path oldApk = Path.of(oldField.getText());
        Path oldModApk = Path.of(oldModField.getText());
        Path newApk = Path.of(newField.getText());
        Path outApk = Path.of(outField.getText());
        resultArea.setText("");
        try {
            Map<String, String> oldMap = buildHashMap(oldApk);
            Map<String, byte[]> modMap = loadEntries(oldModApk);
            Set<String> changed = new HashSet<>();
            for (Map.Entry<String, byte[]> e : modMap.entrySet()) {
                String name = e.getKey();
                byte[] data = e.getValue();
                String orig = oldMap.get(name);
                if (orig == null || !orig.equals(md5(data))) {
                    changed.add(name);
                }
            }
            try (ZipInputStream zin = new ZipInputStream(Files.newInputStream(newApk));
                 ZipOutputStream zout = new ZipOutputStream(Files.newOutputStream(outApk))) {
                ZipEntry ent;
                Set<String> processed = new HashSet<>();
                while ((ent = zin.getNextEntry()) != null) {
                    if (changed.contains(ent.getName())) {
                        byte[] data = modMap.get(ent.getName());
                        if (data != null) {
                            zout.putNextEntry(new ZipEntry(ent.getName()));
                            zout.write(data);
                            processed.add(ent.getName());
                        }
                    } else if (!modMap.containsKey(ent.getName()) || oldMap.containsKey(ent.getName())) {
                        zout.putNextEntry(new ZipEntry(ent.getName()));
                        copyStream(zin, zout);
                    }
                }
                for (String name : changed) {
                    if (!processed.contains(name)) {
                        zout.putNextEntry(new ZipEntry(name));
                        zout.write(modMap.get(name));
                    }
                }
            }
            resultArea.setText(NLS.str("patch_dialog.success", outApk));
        } catch (Exception e) {
            resultArea.setText("Error: " + e.getMessage());
        }
    }

    private Map<String, byte[]> loadEntries(Path apk) throws Exception {
        Map<String, byte[]> map = new HashMap<>();
        ZipReader reader = new ZipReader();
        reader.readEntries(apk.toFile(), (entry, in) -> {
            try {
                map.put(entry.getName(), in.readAllBytes());
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });
        return map;
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

    private static void copyStream(java.io.InputStream in, java.io.OutputStream out) throws Exception {
        byte[] buf = new byte[8192];
        int r;
        while ((r = in.read(buf)) != -1) {
            out.write(buf, 0, r);
        }
    }

    private JButton makeBrowseButton(JTextField field, boolean save) {
        JButton button = new JButton("...");
        button.addActionListener(e -> {
            FileDialogWrapper fd = new FileDialogWrapper(mainWindow, save ? FileOpenMode.CUSTOM_SAVE : FileOpenMode.CUSTOM_OPEN);
            List<Path> files = fd.show();
            if (!files.isEmpty()) {
                field.setText(files.get(0).toString());
            }
        });
        return button;
    }

    private JPanel makeFileRow(String label, JTextField field, boolean save) {
        JLabel lbl = new JLabel(label);
        JPanel row = new JPanel();
        row.setLayout(new BoxLayout(row, BoxLayout.LINE_AXIS));
        row.add(lbl);
        row.add(Box.createRigidArea(new Dimension(5, 0)));
        row.add(field);
        row.add(Box.createRigidArea(new Dimension(5, 0)));
        row.add(makeBrowseButton(field, save));
        return row;
    }

    private void initUI() {
        oldField = new JTextField(30);
        oldModField = new JTextField(30);
        newField = new JTextField(30);
        outField = new JTextField(30);
        resultArea = new JTextArea();
        resultArea.setEditable(false);

        JPanel fields = new JPanel();
        fields.setLayout(new BoxLayout(fields, BoxLayout.PAGE_AXIS));
        fields.add(makeFileRow(NLS.str("patch_dialog.old_apk"), oldField, false));
        fields.add(Box.createRigidArea(new Dimension(0, 5)));
        fields.add(makeFileRow(NLS.str("patch_dialog.old_mod_apk"), oldModField, false));
        fields.add(Box.createRigidArea(new Dimension(0, 5)));
        fields.add(makeFileRow(NLS.str("patch_dialog.new_apk"), newField, false));
        fields.add(Box.createRigidArea(new Dimension(0, 5)));
        fields.add(makeFileRow(NLS.str("patch_dialog.out_apk"), outField, true));
        fields.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));

        JButton patchBtn = new JButton(NLS.str("patch_dialog.patch"));
        patchBtn.addActionListener(e -> patch());

        JPanel buttons = new JPanel();
        buttons.setLayout(new BoxLayout(buttons, BoxLayout.LINE_AXIS));
        buttons.add(Box.createHorizontalGlue());
        buttons.add(patchBtn);
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

        setTitle(NLS.str("patch_dialog.title"));
        commonWindowInit();
    }
}
