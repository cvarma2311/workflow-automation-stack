package com.java.engine;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.stream.Stream;

public class DataFilter {

    public static void main(String[] args) {
        if (args.length != 2) {
            System.err.println("Usage: DataFilter <input_file_path> <output_file_path>");
            System.exit(1);
        }

        String inputPath = args[0];
        String outputPath = args[1];
        int filterDivisor = 10;

        System.out.println("Starting data filtering from " + inputPath + " to " + outputPath);

        try (Stream<String> lines = Files.lines(Paths.get(inputPath));
             BufferedWriter writer = Files.newBufferedWriter(Paths.get(outputPath))) {

            lines.filter(line -> line.hashCode() % filterDivisor == 0)
                 .forEach(line -> {
                     try {
                         writer.write(line);
                         writer.newLine();
                     } catch (IOException e) {
                         throw new RuntimeException("Error writing line to output file", e);
                     }
                 });

        } catch (IOException e) {
            System.err.println("Failed to read or write file.");
            e.printStackTrace();
            System.exit(1);
        }

        System.out.println("Successfully filtered data.");
    }
}
