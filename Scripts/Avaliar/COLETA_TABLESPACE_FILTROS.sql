SELECT
    a.tablespace_name,
    TO_CHAR(SUM(a.bytes)/1024/1024,'999999999999999') max_mb,
    TO_CHAR( (SUM(a.bytes) - c.free)/1024/1024,'999999999999999') used_mb,
    TO_CHAR(c.free/1024/1024,'999999999999999') free_mb,
    round( ( (100 * (SUM(a.bytes) - c.free) ) / SUM(a.bytes) ) ) used_pct,
    CASE
            WHEN (
                SELECT
                    distinct b.autoextensible
                FROM
                    dba_data_files b
                WHERE
                    b.autoextensible = 'NO'
                AND b.tablespace_name = a.tablespace_name
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                           distinct b.maxbytes
                        FROM
                            dba_data_files b
                        WHERE
                            b.maxbytes = 0
                        AND b.tablespace_name = a.tablespace_name
                    ) = 0 THEN TO_CHAR(SUM(a.bytes)/1024/1024,'999999999999999')
                    ELSE TO_CHAR(SUM(a.maxbytes)/1024/1024,'999999999999999')
                END
            )
            ELSE TO_CHAR(SUM(a.maxbytes)/1024/1024,'999999999999999')
        END
    max_autoext_mb,
    CASE
            WHEN (
                SELECT
                    distinct b.autoextensible
                FROM
                    dba_data_files b
                WHERE
                    b.autoextensible = 'NO'
                AND b.tablespace_name = a.tablespace_name
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                            distinct b.maxbytes
                        FROM
                            dba_data_files b
                        WHERE
                            b.maxbytes = 0
                        AND b.tablespace_name = a.tablespace_name
                    ) = 0 THEN TO_CHAR( (SUM(a.bytes) - c.free)/1024/1024,'999999999999999')
                    ELSE TO_CHAR( (SUM(a.maxbytes) - (SUM(a.maxbytes) - SUM(a.bytes) ) )/1024/1024,'999999999999999')
                END
            )
            ELSE TO_CHAR( (SUM(a.maxbytes) - (SUM(a.maxbytes) - SUM(a.bytes) ) )/1024/1024,'999999999999999')
        END
    used_autoext_mb,
    CASE
            WHEN (
                SELECT
                   distinct b.autoextensible
                FROM
                    dba_data_files b
                WHERE
                    b.autoextensible = 'NO'
                AND b.tablespace_name = a.tablespace_name
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                           distinct b.maxbytes
                        FROM
                            dba_data_files b
                        WHERE
                            b.maxbytes = 0
                        AND b.tablespace_name = a.tablespace_name
                    ) = 0 THEN TO_CHAR(c.free/1024/1024,'999999999999999')
                    ELSE TO_CHAR( (SUM(a.maxbytes) - SUM(a.bytes) )/1024/1024,'999999999999999')
                END
            )
            ELSE TO_CHAR( (SUM(a.maxbytes) - SUM(a.bytes) )/1024/1024,'999999999999999')
        END
    free_autoext_mb,
    CASE
            WHEN (
                SELECT
                   distinct b.autoextensible
                FROM
                    dba_data_files b
                WHERE
                    b.autoextensible = 'NO'
                AND b.tablespace_name = a.tablespace_name
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                           distinct b.maxbytes
                        FROM
                            dba_data_files b
                        WHERE
                            b.maxbytes = 0
                        AND b.tablespace_name = a.tablespace_name
                    ) = 0 THEN round( ( (100 * (SUM(a.bytes) - c.free) ) / SUM(a.bytes) ) )
                    ELSE round( (100 * (SUM(a.maxbytes) - (SUM(a.maxbytes) - SUM(a.bytes) ) ) / SUM(a.maxbytes) ) )
                END
            )
            ELSE round( (100 * (SUM(a.maxbytes) - (SUM(a.maxbytes) - SUM(a.bytes) ) ) / SUM(a.maxbytes) ) )
        END
    used_pct_autoext,
    CASE
            WHEN (
                SELECT
                   distinct b.autoextensible
                FROM
                    dba_data_files b
                WHERE
                    b.autoextensible = 'NO'
                AND b.tablespace_name = a.tablespace_name
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                           distinct b.maxbytes
                        FROM
                            dba_data_files b
                        WHERE
                            b.maxbytes = 0
                        AND b.tablespace_name = a.tablespace_name
                    ) = 0 THEN (
                        CASE
                            WHEN round(SUM(a.bytes) / 1024 / 1024) > 10000                    THEN (
                                CASE
                                    WHEN round(SUM(a.bytes) / 1024 / 1024) > 25000                    THEN (
                                        CASE
                                            WHEN round(SUM(a.bytes) / 1024 / 1024) > 50000                    THEN (
                                                CASE
                                                    WHEN round( (SUM(a.bytes) - (SUM(a.bytes) - c.free) ) / 1024 / 1024) < 5000 THEN (
                                                        CASE
                                                            WHEN round( ( (100 * (SUM(a.bytes) - c.free) ) / SUM(a.bytes) ) ) > 80 THEN 'TBS CRITICAL S/AUTO'
                                                            ELSE 'TBS OK S/AUTO'
                                                        END
                                                    )
                                                    ELSE 'TBS OK S/AUTO'
                                                END
                                            )
                                            ELSE (
                                                CASE
                                                    WHEN round( (SUM(a.bytes) - (SUM(a.bytes) - c.free) ) / 1024 / 1024) < 3000 THEN (
                                                        CASE
                                                            WHEN round( ( (100 * (SUM(a.bytes) - c.free) ) / SUM(a.bytes) ) ) > 80 THEN 'TBS CRITICAL S/AUTO'
                                                            ELSE 'TBS OK S/AUTO'
                                                        END
                                                    )
                                                    ELSE 'TBS OK S/AUTO'
                                                END
                                            )
                                        END
                                    )
                                    ELSE (
                                        CASE
                                            WHEN round( (SUM(a.bytes) - (SUM(a.bytes) - c.free) ) / 1024 / 1024) < 1500 THEN (
                                                CASE
                                                    WHEN round( ( (100 * (SUM(a.bytes) - c.free) ) / SUM(a.bytes) ) ) > 80 THEN 'TBS CRITICAL S/AUTO'
                                                    ELSE 'TBS OK S/AUTO'
                                                END
                                            )
                                            ELSE 'TBS OK S/AUTO'
                                        END
                                    )
                                END
                            )
                            ELSE (
                                CASE
                                    WHEN round( (SUM(a.bytes) - (SUM(a.bytes) - c.free) ) / 1024 / 1024) < 500 THEN (
                                        CASE
                                            WHEN round( ( (100 * (SUM(a.bytes) - c.free) ) / SUM(a.bytes) ) ) > 80 THEN 'TBS CRITICAL S/AUTO'
                                            ELSE 'TBS OK S/AUTO'
                                        END
                                    )
                                    ELSE 'TBS OK S/AUTO'
                                END
                            )
                        END
                    )
                    ELSE (
                        CASE
                            WHEN round(SUM(a.maxbytes) / 1024 / 1024) > 10000             THEN (
                                CASE
                                    WHEN round(SUM(a.maxbytes) / 1024 / 1024) > 25000             THEN (
                                        CASE
                                            WHEN round(SUM(a.maxbytes) / 1024 / 1024) > 50000             THEN (
                                                CASE
                                                    WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 5000 THEN 'TBS CRITICAL'
                                                    ELSE 'TBS OK'
                                                END
                                            )
                                            ELSE (
                                                CASE
                                                    WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 3000 THEN 'TBS CRITICAL'
                                                    ELSE 'TBS OK'
                                                END
                                            )
                                        END
                                    )
                                    ELSE (
                                        CASE
                                            WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 1500 THEN 'TBS CRITICAL'
                                            ELSE 'TBS OK'
                                        END
                                    )
                                END
                            )
                            ELSE (
                                CASE
                                    WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 500 THEN 'TBS CRITICAL'
                                    ELSE 'TBS OK'
                                END
                            )
                        END
                    )
                END
            )
            ELSE (
                CASE
                    WHEN round(SUM(a.maxbytes) / 1024 / 1024) > 10000             THEN (
                        CASE
                            WHEN round(SUM(a.maxbytes) / 1024 / 1024) > 25000             THEN (
                                CASE
                                    WHEN round(SUM(a.maxbytes) / 1024 / 1024) > 50000             THEN (
                                        CASE
                                            WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 5000 THEN 'TBS CRITICAL'
                                            ELSE 'TBS OK'
                                        END
                                    )
                                    ELSE (
                                        CASE
                                            WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 3000 THEN 'TBS CRITICAL'
                                            ELSE 'TBS OK'
                                        END
                                    )
                                END
                            )
                            ELSE (
                                CASE
                                    WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 1500 THEN 'TBS CRITICAL'
                                    ELSE 'TBS OK'
                                END
                            )
                        END
                    )
                    ELSE (
                        CASE
                            WHEN round( ( (SUM(a.maxbytes) - SUM(a.bytes) ) ) / 1024 / 1024) < 500 THEN 'TBS CRITICAL'
                            ELSE 'TBS OK'
                        END
                    )
                END
            )
        END
    tbs_critical
FROM
    dba_data_files a,
    sys.filext$ b,
    (
        SELECT
            d.tablespace_name,
            SUM(nvl(c.bytes,0) ) free
        FROM
            dba_tablespaces d,
            dba_free_space c
        WHERE
            d.tablespace_name = c.tablespace_name (+)
        GROUP BY
            d.tablespace_name
    ) c
WHERE
    a.file_id = b.file# (+)
    AND   a.tablespace_name = c.tablespace_name
GROUP BY
    a.tablespace_name,
    c.free
UNION ALL
SELECT
    f.tablespace_name,
    TO_CHAR( (SUM(e.bytes) )/1024/1024,'999999999999999') max_mb,
    TO_CHAR( (SUM(f.bytes_used) )/1024/1024,'999999999999999') used_mb,
    TO_CHAR( (SUM(f.bytes_free) )/1024/1024,'999999999999999') free_mb,
    round( (100 * (SUM(f.bytes_used) ) ) / SUM(e.bytes) ) used_pct,
    CASE
            WHEN (
                SELECT
                   distinct b.autoextensible
                FROM
                    dba_temp_files b
                WHERE
                    b.autoextensible = 'NO'
                AND b.tablespace_name = f.tablespace_name
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                           distinct b.maxbytes
                        FROM
                            dba_temp_files b
                        WHERE
                            b.maxbytes = 0
                        AND b.tablespace_name = f.tablespace_name
                    ) = 0 THEN TO_CHAR(SUM(e.bytes)/1024/1024,'999999999999999')
                    ELSE TO_CHAR(SUM(e.maxbytes)/1024/1024,'999999999999999')
                END
            )
            ELSE TO_CHAR(SUM(e.maxbytes)/1024/1024,'999999999999999')
        END
    max_autoext_mb,
    CASE
            WHEN (
                SELECT
                   distinct b.autoextensible
                FROM
                    dba_temp_files b
                WHERE
                    b.autoextensible = 'NO'
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                          distinct b.maxbytes
                        FROM
                            dba_temp_files b
                        WHERE
                            b.maxbytes = 0
                    ) = 0 THEN TO_CHAR( (SUM(f.bytes_used) )/1024/1024,'999999999999999')
                    ELSE TO_CHAR( (SUM(e.maxbytes) - (SUM(e.maxbytes) - SUM(e.bytes) ) )/1024/1024,'999999999999999')
                END
            )
            ELSE TO_CHAR( (SUM(e.maxbytes) - (SUM(e.maxbytes) - SUM(e.bytes) ) )/1024/1024,'999999999999999')
        END
    used_autoext_mb,
    CASE
            WHEN (
                SELECT
                   distinct b.autoextensible
                FROM
                    dba_temp_files b
                WHERE
                    b.autoextensible = 'NO'
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                           distinct b.maxbytes
                        FROM
                            dba_temp_files b
                        WHERE
                            b.maxbytes = 0
                    ) = 0 THEN TO_CHAR( (SUM(f.bytes_free) )/1024/1024,'999999999999999')
                    ELSE TO_CHAR( ( (SUM(e.maxbytes) - SUM(e.bytes) ) )/1024/1024,'999999999999999')
                END
            )
            ELSE TO_CHAR( ( (SUM(e.maxbytes) - SUM(e.bytes) ) )/1024/1024,'999999999999999')
        END
    free_autoext_mb,
    CASE
            WHEN (
                SELECT
                   distinct b.autoextensible
                FROM
                    dba_temp_files b
                WHERE
                    b.autoextensible = 'NO'
            ) = 'NO' THEN (
                CASE
                    WHEN (
                        SELECT
                           distinct b.maxbytes
                        FROM
                            dba_temp_files b
                        WHERE
                            b.maxbytes = 0
                    ) = 0 THEN round( (100 * (SUM(f.bytes_used) ) ) / SUM(e.bytes) )
                    ELSE round( (100 * (SUM(e.maxbytes) - (SUM(e.maxbytes) - SUM(e.bytes) ) ) / SUM(e.maxbytes) ) )
                END
            )
            ELSE round( (100 * (SUM(e.maxbytes) - (SUM(e.maxbytes) - SUM(e.bytes) ) ) / SUM(e.maxbytes) ) )
        END
    used_pct_autoext,
    CASE
            WHEN SUM(f.bytes_used) > ( SUM(e.maxbytes) * 90 ) / 100 THEN 'TBS TEMP'
            ELSE 'TBS TEMP'
        END
    tbs_critical
FROM
    v$temp_space_header f,
    dba_temp_files e
WHERE
    e.file_id = f.file_id (+)
GROUP BY
    f.tablespace_name
ORDER BY
    1