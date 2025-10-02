#traceability point 02 test_tvrdosti
CHECK (EXISTS (SELECT 1 FROM ICE_Data WHERE DPM_Code = Scanned_Part.DPM_Code)) CHECK (EXISTS (SELECT 1 FROM Tr_Points WHERE (Point_ID IN (1,2) AND Status = 'OK')) AND Current_Status <> 'NOK')

#traceability point 03 Penetrace
EXISTS (
        SELECT 1 
        FROM (
            SELECT 
                CASE 
                    WHEN status = 'OK' THEN 'OK'
                    WHEN status = 'NOK' THEN 'NOK'
                    WHEN status = 'REWORK' THEN 'REWORK'
                    ELSE 'UNKNOWN'
                END as status,
                CASE 
                    WHEN status = 'OK' THEN NULL
                    WHEN status = 'NOK' THEN 'Díl neproslo kontrolou na pracovisti Test tvrdosti. Pro bližší informace použijte Info režim.'
                    WHEN status = 'REWORK' THEN 'Díl je urcen k prepracování (REWORK) z pracovište Test tvrdosti. Pro bližší informace použijte Info režim.'
                    WHEN status IS NULL THEN 'Díl nemá žádný záznam z pracovište Test tvrdosti. Nejprve musí projít testem tvrdosti.'
                    ELSE 'Neznámý status z pracovište Test tvrdosti. Kontaktujte vedoucího smeny.'
                END as error_message
            FROM dbo.h_part_status 
            WHERE part_id = Current_Part_ID 
            AND workspace_id = 2
            AND status_timestamp = (
                SELECT MAX(status_timestamp) 
                FROM dbo.h_part_status 
                WHERE part_id = Current_Part_ID 
                AND workspace_id = 2
            )
        ) s
        WHERE s.status = 'OK'
    )
#traceability point 04 tryskani
CHECK (EXISTS (SELECT 1 FROM Gitterbox WHERE Scanned = 1)) CHECK (EXISTS (SELECT 1 FROM Part_Status WHERE Part_ID = Current_Part_ID AND (Tr_Point = 'Penetration' OR Tr_Point = 'Blasting rework') AND Status = 'OK')) CHECK (EXISTS (SELECT 1 FROM Gitterbox WHERE Current_Load < Max_Capacity))

#traceability point 05 Kontrola kvality
CHECK (EXISTS (SELECT 1 FROM Part_Status WHERE Part_ID = Current_Part_ID AND Status = 'OK'))

#traceability point 07 Laborator
CHECK (EXISTS (SELECT 1 FROM ICE_Data WHERE DPM_Code = Scanned_Part.DPM_Code))

#traceability point 08 Penetrace_Rework
CHECK (EXISTS (SELECT 1 FROM Part_Status WHERE Part_ID = Current_Part_ID AND Tr_Point = 'Penetration test' AND Status = 'REWORK'))

#traceability point 09 Blasting_Rework
CHECK (EXISTS (SELECT 1 FROM Part_Status WHERE Part_ID = Current_Part_ID AND Tr_Point = 'Blasting test' AND Status = 'REWORK'))

#traceability point 10 Kontrola Kvality Rework
CHECK (EXISTS (SELECT 1 FROM Part_Status WHERE Part_ID = Current_Part_ID AND Tr_Point = 'Blasting test' AND Status = 'REWORK'))

