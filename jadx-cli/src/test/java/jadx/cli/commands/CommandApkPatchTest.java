package jadx.cli.commands;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

import com.beust.jcommander.JCommander;

import jadx.cli.JadxCLIArgs;
import jadx.cli.JCommanderWrapper;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import static org.assertj.core.api.Assertions.assertThat;

public class CommandApkPatchTest {

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
    public void testApkPatch() throws Exception {
        Path oldZip = createZip(dir.resolve("old.zip"), "a.txt", "1");
        Path oldModZip = createZip(dir.resolve("oldmod.zip"), "a.txt", "2");
        Path newZip = dir.resolve("new.zip");
        try (ZipOutputStream zout = new ZipOutputStream(Files.newOutputStream(newZip))) {
            zout.putNextEntry(new ZipEntry("a.txt"));
            zout.write("1".getBytes(StandardCharsets.UTF_8));
            zout.putNextEntry(new ZipEntry("b.txt"));
            zout.write("b".getBytes(StandardCharsets.UTF_8));
        }
        Path outZip = dir.resolve("out.zip");

        CommandApkPatch cmd = new CommandApkPatch();
        JCommander jc = JCommander.newBuilder().addCommand(cmd.name(), cmd).build();
        jc.parse(cmd.name(), "--old", oldZip.toString(), "--old-mod", oldModZip.toString(),
                "--new", newZip.toString(), "--out", outZip.toString());
        JCommander sub = jc.getCommands().get(cmd.name());

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        PrintStream oldOut = System.out;
        System.setOut(new PrintStream(out));
        try {
            cmd.process(new JCommanderWrapper(new JadxCLIArgs()), sub);
        } finally {
            System.setOut(oldOut);
        }

        try (ZipInputStream zin = new ZipInputStream(Files.newInputStream(outZip))) {
            ZipEntry ent;
            String aContent = null;
            String bContent = null;
            while ((ent = zin.getNextEntry()) != null) {
                ByteArrayOutputStream buf = new ByteArrayOutputStream();
                zin.transferTo(buf);
                if (ent.getName().equals("a.txt")) {
                    aContent = buf.toString(StandardCharsets.UTF_8);
                } else if (ent.getName().equals("b.txt")) {
                    bContent = buf.toString(StandardCharsets.UTF_8);
                }
            }
            assertThat(aContent).isEqualTo("2");
            assertThat(bContent).isEqualTo("b");
        }
    }
}
