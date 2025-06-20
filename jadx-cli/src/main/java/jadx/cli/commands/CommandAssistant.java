package jadx.cli.commands;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;

import com.beust.jcommander.JCommander;
import com.beust.jcommander.Parameter;
import com.beust.jcommander.Parameters;

import jadx.cli.JCommanderWrapper;
import jadx.api.plugins.utils.CommonFileUtils;

@Parameters(commandDescription = "ask AI assistant (OpenAI API)")
public class CommandAssistant implements ICommand {
    @Parameter(names = {"-q", "--question"}, description = "question text")
    private String question;

    @Parameter(names = {"--model"}, description = "openai model id")
    private String model = "gpt-3.5-turbo";

    @Parameter(names = {"-h", "--help"}, help = true, description = "print this help")
    private boolean help;

    @Override
    public String name() {
        return "assistant";
    }

    @Override
    public void process(JCommanderWrapper jcw, JCommander sub) {
        if (help || question == null) {
            jcw.printUsage(sub);
            return;
        }
        String apiKey = System.getenv("OPENAI_API_KEY");
        if (apiKey == null || apiKey.isEmpty()) {
            System.out.println("OPENAI_API_KEY environment variable not set");
            return;
        }
        try {
            HttpURLConnection con = (HttpURLConnection) URI.create("https://api.openai.com/v1/chat/completions").toURL().openConnection();
            con.setRequestMethod("POST");
            con.setRequestProperty("Authorization", "Bearer " + apiKey);
            con.setRequestProperty("Content-Type", "application/json");
            con.setDoOutput(true);
            String payload = String.format("{\"model\":\"%s\",\"messages\":[{\"role\":\"user\",\"content\":%s}]}", model, quote(question));
            try (OutputStream out = con.getOutputStream()) {
                out.write(payload.getBytes(StandardCharsets.UTF_8));
            }
            int code = con.getResponseCode();
            try (var in = code >= 200 && code < 300 ? con.getInputStream() : con.getErrorStream()) {
                String response = new String(CommonFileUtils.loadBytes(in), StandardCharsets.UTF_8);
                System.out.println(response);
            }
        } catch (Exception e) {
            throw new RuntimeException("AI request failed", e);
        }
    }

    private static String quote(String str) {
        return '"' + str.replace("\\", "\\\\").replace("\"", "\\\"") + '"';
    }
}
