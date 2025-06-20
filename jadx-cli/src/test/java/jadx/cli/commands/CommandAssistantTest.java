package jadx.cli.commands;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLConnection;
import java.net.URLStreamHandler;
import java.net.URLStreamHandlerFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;

import com.beust.jcommander.JCommander;

import jadx.cli.JadxCLIArgs;
import jadx.cli.JCommanderWrapper;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

public class CommandAssistantTest {

    static class MockHttpURLConnection extends HttpURLConnection {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int responseCode = 200;
        String response = "{}";

        MockHttpURLConnection(URL u) { super(u); }
        @Override public void disconnect() {}
        @Override public boolean usingProxy() { return false; }
        @Override public void connect() {}
        @Override public OutputStream getOutputStream() { return out; }
        @Override public InputStream getInputStream() { return new ByteArrayInputStream(response.getBytes(StandardCharsets.UTF_8)); }
        @Override public InputStream getErrorStream() { return getInputStream(); }
        @Override public int getResponseCode() { return responseCode; }
    }

    private static MockHttpURLConnection lastCon;

    @BeforeAll
    static void installFactory() {
        try {
            URL.setURLStreamHandlerFactory(new URLStreamHandlerFactory() {
                @Override
                public URLStreamHandler createURLStreamHandler(String protocol) {
                    if ("https".equals(protocol)) {
                        return new URLStreamHandler() {
                            @Override
                            protected URLConnection openConnection(URL u) {
                                lastCon = new MockHttpURLConnection(u);
                                return lastCon;
                            }
                        };
                    }
                    return null;
                }
            });
        } catch (Error ignore) {
        }
    }

    @Test
    public void testRequestFormatting() throws Exception {
        ProcessBuilder pb = new ProcessBuilder(
                Path.of(System.getProperty("java.home"), "bin", "java").toString(),
                "-cp", System.getProperty("java.class.path"),
                Runner.class.getName());
        pb.environment().put("OPENAI_API_KEY", "token");
        Process proc = pb.start();
        byte[] out = proc.getInputStream().readAllBytes();
        proc.getErrorStream().transferTo(System.err);
        int code = proc.waitFor();
        assertThat(code).isEqualTo(0);
        String res = new String(out, StandardCharsets.UTF_8);
        assertThat(res).contains("BODY:");
        assertThat(res).contains("\"content\":\"hi\"");
        assertThat(res).contains("AUTH:Bearer token");
    }

    public static class Runner {
        public static void main(String[] args) throws Exception {
            // install handler in subprocess
            try {
                URL.setURLStreamHandlerFactory(new URLStreamHandlerFactory() {
                    @Override
                    public URLStreamHandler createURLStreamHandler(String protocol) {
                        if ("https".equals(protocol)) {
                            return new URLStreamHandler() {
                                @Override
                                protected URLConnection openConnection(URL u) {
                                    lastCon = new MockHttpURLConnection(u);
                                    return lastCon;
                                }
                            };
                        }
                        return null;
                    }
                });
            } catch (Error ignore) {
            }
            CommandAssistant cmd = new CommandAssistant();
            JCommander jc = JCommander.newBuilder().addCommand(cmd.name(), cmd).build();
            jc.parse(cmd.name(), "-q", "hi");
            JCommander sub = jc.getCommands().get(cmd.name());
            ByteArrayOutputStream bout = new ByteArrayOutputStream();
            PrintStream old = System.out;
            System.setOut(new PrintStream(bout));
            try {
                cmd.process(new JCommanderWrapper(new JadxCLIArgs()), sub);
            } finally {
                System.setOut(old);
            }
            if (lastCon != null) {
                String body = lastCon.out.toString(StandardCharsets.UTF_8);
                String auth = lastCon.getRequestProperty("Authorization");
                System.out.println("BODY:" + body);
                System.out.println("AUTH:" + auth);
            }
        }
    }
}
