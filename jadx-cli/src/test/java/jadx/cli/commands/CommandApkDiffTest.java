package jadx.cli.commands;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import com.beust.jcommander.JCommander;

import jadx.cli.JadxCLIArgs;
import jadx.cli.JCommanderWrapper;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import static org.assertj.core.api.Assertions.assertThat;

public class CommandApkDiffTest {

    @TempDir
    Path dir;

    private Path createZip(Path path, String name, String content) throws Exception {
        try (ZipOutputStream zout = new ZipOutputStream(Files.newOutputStream(path))) {
            zout.putNextEntry(new ZipEntry(name));
            zout.write(content.getBytes(StandardCharsets.UTF_8));
        }
        return path;
    }

    @Test
    public void testApkDiff() throws Exception {
        Path oldZip = createZip(dir.resolve("old.zip"), "a.txt", "1");
        Path newZip = createZip(dir.resolve("new.zip"), "a.txt", "2");

        CommandApkDiff cmd = new CommandApkDiff();
        JCommander jc = JCommander.newBuilder().addCommand(cmd.name(), cmd).build();
        jc.parse(cmd.name(), "--old", oldZip.toString(), "--new", newZip.toString());
        JCommander sub = jc.getCommands().get(cmd.name());

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        PrintStream old = System.out;
        System.setOut(new PrintStream(out));
        try {
            cmd.process(new JCommanderWrapper(new JadxCLIArgs()), sub);
        } finally {
            System.setOut(old);
        }

        String result = out.toString(StandardCharsets.UTF_8);
        assertThat(result.trim()).contains("CHANGED a.txt");
    }
}
