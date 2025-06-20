package jadx.cli.commands;

import com.beust.jcommander.JCommander;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Field;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLConnection;
import java.net.URLStreamHandler;
import java.net.URLStreamHandlerFactory;
import java.nio.charset.StandardCharsets;
import java.util.Map;

import jadx.cli.JCommanderWrapper;
import jadx.cli.JadxCLIArgs;

import static org.assertj.core.api.Assertions.assertThat;

public class CommandAssistantTest {
    private static MockHttpURLConnection lastConnection;

    @BeforeAll
    public static void installFactory() {
        try {
            URL.setURLStreamHandlerFactory(new MockFactory());
        } catch (Error ignore) {
            // factory already set
        }
    }

    @AfterEach
    public void clear() {
        lastConnection = null;
    }

    @Test
    public void testRequestFormat() throws Exception {
        setEnv("OPENAI_API_KEY", "t");
        try {
            CommandAssistant cmd = new CommandAssistant();
            JCommander jc = JCommander.newBuilder()
                    .addCommand(cmd.name(), cmd)
                    .build();
            jc.parse(cmd.name(), "-q", "Hello");
            JCommander sub = jc.getCommands().get(cmd.name());

            cmd.process(new JCommanderWrapper(new JadxCLIArgs()), sub);

            assertThat(lastConnection).isNotNull();
            String payload = lastConnection.sent.toString(StandardCharsets.UTF_8);
            assertThat(lastConnection.method).isEqualTo("POST");
            assertThat(payload).contains("\"content\":\"Hello\"");
        } finally {
            unsetEnv("OPENAI_API_KEY");
        }
    }

    private static class MockFactory implements URLStreamHandlerFactory {
        @Override
        public URLStreamHandler createURLStreamHandler(String protocol) {
            if ("https".equals(protocol)) {
                return new URLStreamHandler() {
                    @Override
                    protected URLConnection openConnection(URL u) {
                        if (u.getHost().equals("api.openai.com")) {
                            lastConnection = new MockHttpURLConnection(u);
                            return lastConnection;
                        }
                        throw new RuntimeException("Unexpected URL: " + u);
                    }
                };
            }
            return null;
        }
    }

    private static class MockHttpURLConnection extends HttpURLConnection {
        final ByteArrayOutputStream sent = new ByteArrayOutputStream();
        String method;
        MockHttpURLConnection(URL u) { super(u); }
        @Override public void disconnect() { }
        @Override public boolean usingProxy() { return false; }
        @Override public void connect() { }
        @Override public void setRequestMethod(String method) { this.method = method; }
        @Override public OutputStream getOutputStream() { return sent; }
        @Override public int getResponseCode() { return 200; }
        @Override public InputStream getInputStream() { return new ByteArrayInputStream("{}".getBytes(StandardCharsets.UTF_8)); }
    }

    // Unsafe environment update utilities
    private static final sun.misc.Unsafe UNSAFE;
    static {
        try {
            Field f = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
            f.setAccessible(true);
            UNSAFE = (sun.misc.Unsafe) f.get(null);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> envMap(String field) throws Exception {
        Class<?> pe = Class.forName("java.lang.ProcessEnvironment");
        Field f = pe.getDeclaredField(field);
        Object obj = UNSAFE.getObject(pe, UNSAFE.staticFieldOffset(f));
        Field m = obj.getClass().getDeclaredField("m");
        return (Map<String, String>) UNSAFE.getObject(obj, UNSAFE.objectFieldOffset(m));
    }

    private static void setEnv(String k, String v) throws Exception {
        envMap("theUnmodifiableEnvironment").put(k, v);
        try { envMap("theCaseInsensitiveEnvironment").put(k, v); } catch (Exception ignore) { }
    }

    private static void unsetEnv(String k) throws Exception {
        envMap("theUnmodifiableEnvironment").remove(k);
        try { envMap("theCaseInsensitiveEnvironment").remove(k); } catch (Exception ignore) { }
    }
}
