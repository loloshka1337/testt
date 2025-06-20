package jadx.cli;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

public class AddCommandTest {
    @Test
    public void testAddCommand() {
        PrintStream oldOut = System.out;
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        System.setOut(new PrintStream(out));
        try {
            int result = JadxCLI.execute(new String[]{"add", "--a", "2", "--b", "3"});
            assertThat(result).isEqualTo(0);
        } finally {
            System.setOut(oldOut);
        }
        assertThat(out.toString().trim()).isEqualTo("5");
    }
}
