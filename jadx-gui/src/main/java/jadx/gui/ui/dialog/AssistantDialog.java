package jadx.gui.ui.dialog;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;

import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;

import jadx.gui.ui.MainWindow;
import jadx.gui.utils.NLS;
import jadx.api.plugins.utils.CommonFileUtils;

public class AssistantDialog extends CommonDialog {
    private static final long serialVersionUID = -1L;

    private JTextArea questionArea;
    private JTextArea answerArea;

    public AssistantDialog(MainWindow mainWindow) {
        super(mainWindow);
        initUI();
    }

    private void ask() {
        String apiKey = System.getenv("OPENAI_API_KEY");
        if (apiKey == null || apiKey.isEmpty()) {
            answerArea.setText(NLS.str("assistant_dialog.api_key_missing"));
            return;
        }
        try {
            HttpURLConnection con = (HttpURLConnection) URI.create("https://api.openai.com/v1/chat/completions").toURL().openConnection();
            con.setRequestMethod("POST");
            con.setRequestProperty("Authorization", "Bearer " + apiKey);
            con.setRequestProperty("Content-Type", "application/json");
            con.setDoOutput(true);
            String payload = String.format("{\"model\":\"gpt-3.5-turbo\",\"messages\":[{\"role\":\"user\",\"content\":%s}]}", quote(questionArea.getText()));
            try (OutputStream out = con.getOutputStream()) {
                out.write(payload.getBytes(StandardCharsets.UTF_8));
            }
            int code = con.getResponseCode();
            try (var in = code >= 200 && code < 300 ? con.getInputStream() : con.getErrorStream()) {
                String response = new String(CommonFileUtils.loadBytes(in), StandardCharsets.UTF_8);
                answerArea.setText(response);
            }
        } catch (Exception e) {
            answerArea.setText("Error: " + e.getMessage());
        }
    }

    private static String quote(String str) {
        return '"' + str.replace("\\", "\\\\").replace("\"", "\\\"") + '"';
    }

    private void initUI() {
        questionArea = new JTextArea();
        answerArea = new JTextArea();
        answerArea.setEditable(false);

        JPanel top = new JPanel();
        top.setLayout(new BoxLayout(top, BoxLayout.PAGE_AXIS));
        top.add(new JLabel(NLS.str("assistant_dialog.prompt")));
        top.add(new JScrollPane(questionArea));
        top.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));

        JButton sendBtn = new JButton(NLS.str("assistant_dialog.send"));
        sendBtn.addActionListener(e -> ask());
        JButton closeBtn = new JButton(NLS.str("common_dialog.close"));
        closeBtn.addActionListener(e -> dispose());
        JPanel buttons = new JPanel();
        buttons.setLayout(new BoxLayout(buttons, BoxLayout.LINE_AXIS));
        buttons.add(Box.createHorizontalGlue());
        buttons.add(sendBtn);
        buttons.add(Box.createRigidArea(new Dimension(10, 0)));
        buttons.add(closeBtn);
        buttons.setBorder(BorderFactory.createEmptyBorder(0, 10, 10, 10));

        JScrollPane ansScroll = new JScrollPane(answerArea);
        ansScroll.setPreferredSize(new Dimension(500, 300));

        getContentPane().add(top, BorderLayout.PAGE_START);
        getContentPane().add(ansScroll, BorderLayout.CENTER);
        getContentPane().add(buttons, BorderLayout.PAGE_END);

        setTitle(NLS.str("assistant_dialog.title"));
        commonWindowInit();
    }
}
