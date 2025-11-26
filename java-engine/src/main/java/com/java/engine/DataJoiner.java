package com.java.engine;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.HashSet;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class DataJoiner {

    public static void main(String[] args) {
        if (args.length != 3) {
            System.err.println("Usage: DataJoiner <original_file_path> <filtered_ids_path> <output_file_path>");
            System.exit(1);
        }

        String originalFilePath = args[0];
        String filteredIdsPath = args[1];
        String outputPath = args[2];
        long originalFileLimit = 100_000_000L;

        System.out.println("Starting data joining.");

        try {
            // 1. Read all IDs from the smaller, filtered file into a HashSet for efficient lookups.
            System.out.println("Loading IDs from " + filteredIdsPath);
            Set<String> filteredIds;
            try (Stream<String> lines = Files.lines(Paths.get(filteredIdsPath))) {
                filteredIds = lines.map(line -> line.split(",")[0])
                                   .collect(Collectors.toSet());
            }
            System.out.println("Loaded " + filteredIds.size() + " IDs.");

            // 2. Stream the first 100M records of the original file and join.
            System.out.println("Streaming and joining first " + originalFileLimit + " records from " + originalFilePath);
            try (Stream<String> originalLines = Files.lines(Paths.get(originalFilePath)).limit(originalFileLimit);
                 BufferedWriter writer = Files.newBufferedWriter(Paths.get(outputPath))) {

                originalLines.filter(line -> {
                    String id = line.split(",")[0];
                    return filteredIds.contains(id);
                }).forEach(line -> {
                    try {
                        writer.write(line);
                        writer.newLine();
                    } catch (IOException e) {
                        throw new RuntimeException("Error writing joined line to output", e);
                    }
                });
            }
            System.out.println("Successfully joined data to " + outputPath);

        } catch (IOException e) {
            System.err.println("An error occurred during the join process.");
            e.printStackTrace();
            System.exit(1);
        }
    }
}
