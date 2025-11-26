package com.java.engine;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.UUID;
import java.util.stream.Stream;

public class DataGenerator {

    public static void main(String[] args) {
        if (args.length != 1) {
            System.err.println("Usage: DataGenerator <output_file_path>");
            System.exit(1);
        }

        String filePath = args[0];
        long numberOfRecords = 500_000_000L;

        System.out.println("Starting data generation for " + numberOfRecords + " records into " + filePath);

        Stream<String> recordStream = Stream.generate(() ->
                "id:" + UUID.randomUUID() + ",data:some_random_payload_data"
        ).limit(numberOfRecords);

        try (BufferedWriter writer = Files.newBufferedWriter(Paths.get(filePath))) {
            recordStream.forEach(line -> {
                try {
                    writer.write(line);
                    writer.newLine();
                } catch (IOException e) {
                    throw new RuntimeException("Error writing line to file", e);
                }
            });
        } catch (IOException e) {
            System.err.println("Failed to open or write to file: " + filePath);
            e.printStackTrace();
            System.exit(1);
        }

        System.out.println("Successfully generated " + numberOfRecords + " records.");
    }
}
