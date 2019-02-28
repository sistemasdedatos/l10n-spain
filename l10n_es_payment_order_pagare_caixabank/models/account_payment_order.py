# -*- coding: utf-8 -*-
# (c) 2018 Comunitea Servicios Tecnológicos - Javier Colmenero
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models, api, _, fields
from odoo.exceptions import UserError
from datetime import date


class AccountPaymentOrder(models.Model):
    _inherit = "account.payment.order"

    def strim_txt(self, text, size):
        """
        Devuelvo el texto con espacios al final hasta completar size
        """
        if text:
            if len(text) < size:
                relleno = size - len(text)
                text += relleno * ' '
            elif len(text) > size:
                text = text[:size]
        return text

    @api.multi
    def generate_payment_file(self):
        self.ensure_one()
        if self.payment_method_id.code != 'pagare_caixabank':
            return super(AccountPaymentOrder, self).generate_payment_file()
        self.num_lineas = 0
        txt_file = self._pop_cabecera_pagare_caix()
        for line in self.bank_line_ids:
            txt_file += self._pop_beneficiarios_pagare_caix(line)
        txt_file += self._pop_totales_pagare_caix(line, self.num_lineas)
        return self.to_ascii(txt_file).\
            encode('ascii', 'ignore'), self.name + '.csb34'

    def _get_fix_txt(self, mode='cabecera'):
        text = ''
        # 1 - 4: Código registro
        text += '0356' if mode == 'cabecera' else '0659'

        # 5 : Libre
        text += ' '

        # 6 - 14
        vat = self.convert_vat(self.company_partner_bank_id.partner_id)
        text += self.convert(vat, 9)

        # 15 - 17: Libre
        text += 3 * ' '
        return text

    def _get_fecha_planificada(self):
        fecha_planificada = 6 * ' '
        if self.date_prefered == 'due':
            fecha_planificada = self.payment_line_ids \
                and self.payment_line_ids[0].ml_maturity_date \
                or date.today().strftime('%Y-%d-%m')
            fecha_planificada = fields.Date.from_string(fecha_planificada)
        elif self.date_prefered == 'now':
            fecha_planificada = date.today().strftime('%d%m%y')
        else:
            fecha_planificada = self.date_scheduled
            if not fecha_planificada:
                raise UserError(
                    _("Error: Fecha planificada no \
                        establecida en la Orden de pago."))
            else:
                fecha_planificada = fields.Date.from_string(fecha_planificada)
        return fecha_planificada.strftime('%d%m%y')

    def _get_fecha_vencimiento(self, line):
        fecha_vencimiento = 8 * ' '
        if line.date:
            fecha_vencimiento = line.date.replace('-', '')
            dia = fecha_vencimiento[6:]
            mes = fecha_vencimiento[4:6]
            ano = fecha_vencimiento[0:4]
            fecha_vencimiento = dia + mes + ano
        return fecha_vencimiento

    def _pop_cabecera_pagare_caix(self):
        """
        Devuelve las 4 líneas de la cabecera
        """
        fecha_planificada = self._get_fecha_planificada()

        all_text = ''
        for i in range(4):
            text = ''
            text += self._get_fix_txt()
            # 18 - 26: Libre
            text += 9 * ' '
            # 27 - 29: Numero del dato
            dato = '00' + str(i + 1)
            text += dato

            # LINEA 1
            ###################################################################
            if (i + 1) == 1:  # Tipo registro 1, línea 1
                # 30 - 35: Fecha creación del fichero
                today = date.today().strftime('%d%m%y')
                text += today
                # 36 - 41: Otra vez la fecha
                text += today
                cuenta = self.company_partner_bank_id.acc_number
                cuenta = cuenta.replace(' ', '')
                tipo_cuenta = self.company_partner_bank_id.acc_type
                if tipo_cuenta == 'iban':
                    cuenta = cuenta[4:]
                entidad = cuenta[0:4]
                oficina = cuenta[4:8]
                control = cuenta[8:10]
                num_cuenta = cuenta[10:]
                # 42 - 45: Entidad de destino del soporte
                text += entidad
                # 46 - 49: Oficina de destino del soporte
                text += oficina
                # 50 - 59: Número de contrato de confirming
                text += num_cuenta

                # 60: Detalle del cargo
                text += '0'  # segun la documentacvión es 1??
                # 61 - 63: Libre
                text += 3 * ' '
                # 64 - 65: Digitos control
                text += control
                # 66 - 72: Libre
                text += 7 * ' '
            ###################################################################

            # LINEA 2
            ###################################################################
            if (i + 1) == 2:
                ordenante = self.company_partner_bank_id.partner_id.name
                if not ordenante:
                    raise UserError(
                        _("Error: Propietario de la cuenta no establecido para\
                        la cuenta %s.") %
                        self.company_partner_bank_id.acc_number)
                ordenante = self.strim_txt(ordenante, 36)
                text += ordenante.upper()
            ###################################################################

            # LINEA 3
            ###################################################################
            if (i + 1) == 3:
                domicilio_pro = self.company_partner_bank_id.partner_id.street
                if not domicilio_pro:
                    raise UserError(
                        _("Error: El Ordenante %s no tiene \
                        establecido el Domicilio.\
                         ") % self.company_partner_bank_id.partner_id.name)
                domicilio_pro = self.strim_txt(domicilio_pro, 36)

                text += domicilio_pro.upper()
            ###################################################################

            # LINEA 4
            ###################################################################
            if (i + 1) == 4:
                ciudad_pro = self.company_partner_bank_id.partner_id.city
                if not ciudad_pro:
                    raise UserError(
                        _("Error: El Ordenante %s no tiene establecida la \
                        Ciudad.") %
                        self.company_partner_bank_id.partner_id.name)
                ciudad_pro = self.strim_txt(ciudad_pro, 36)
                text += ciudad_pro.upper()
            ###################################################################

            text = text[:72] + '\r\n'
            all_text += text
            self.num_lineas += 1
        return all_text

    def _get_linea_10X(self, mode='101'):
        col1 = 'N. FACTURA'
        col1_2 = ' ' + col1
        sep1 = 6 * ' '
        col2 = 'FECHA'
        sep2 = 7 * ' '
        col3 = 'IMPORTE'
        sep3 = 8 * ' '
        sep3_2 = 7 * ' '

        res = ''
        if mode == '101':
            res = col1 + sep1 + col2 + sep2 + col3 + sep3
        else:
            res = col1_2 + sep1 + col2 + sep2 + col3 + sep3_2
        return res

    def _pop_beneficiarios_pagare_caix(self, line):
        all_text = ''

        idx = 102
        bloque_registros = ['010', '011', '012', '014', '015', '101', '102']
        trans_by_key = {}
        # Añado registros del 103 al 1XX por cada linea de transación
        # asociada a la línea de banco
        for payment_line in line.payment_line_ids:
            idx += 1
            key = str(idx)
            trans_by_key[key] = payment_line
            bloque_registros.append(key)
        # El ultimo registro es el '910'
        bloque_registros.append('910')

        fixed_text = self._get_fix_txt(mode='beneficiario')

        # 18 - 26: Nid del proveedor
        nif = line.partner_id.vat
        if not nif:
            raise UserError(
                _("Error: El Proveedor %s no tiene establecido\
                 el NIF.") % line.partner_id.name)
        nif = self.convert_vat(line.partner_id)

        fixed_text += self.convert(nif, 9)

        for tipo_dato in bloque_registros:
            text = ''
            text += fixed_text
            # 27 - 29 Numero de dato
            text += tipo_dato

            # LÍNEA 1
            ###################################################################
            if tipo_dato == '010':
                # 30 - 41 Importe
                amount_text = self.convert(abs(line.amount_currency), 12)
                text += amount_text

                # 42 - 49: Libre
                text += 8 * ' '
                # 50 - 61 Fijo
                text += '000000010019'
                # 62 - 72: Libre
                text += 11 * ' '
            ###################################################################

            # LÍNEA 2
            ###################################################################
            if tipo_dato == '011':
                # 30 - 65 Nombre del proveedor
                nombre_pro = self.strim_txt(line.partner_id.name, 36)
                text += nombre_pro.upper()
                # 66 - 72 Libre
                text += 7 * ' '
            ###################################################################

            # LÍNEA 3
            ###################################################################
            if tipo_dato == '012':
                # 30 - 65 Domicilio del proveedor
                if not line.partner_id.street:
                    raise UserError(
                        _("Error: El Proveedor %s no tiene\
                         establecido el Domicilio.\
                         ") % line.partner_id.name)
                domicilio_pro = self.strim_txt(
                    line.partner_id.street, 36)
                text += domicilio_pro.upper()
                # 66 - 72 Libre
                text += 7 * ' '
            ###################################################################

            # LÍNEA 4
            ###################################################################
            if tipo_dato == '014':
                # 30 - 34 CP
                if not line.partner_id.zip:
                    raise UserError(
                        _("Error: El Proveedor %s no tiene establecido\
                         el C.P.") % line.partner_id.name)
                cp_pro = self.strim_txt(line.partner_id.zip, 5)
                text += cp_pro.upper()

                # 35 - 65 Plaza del proveedor
                if not line.partner_id.city:
                    raise UserError(
                        _("Error: El Proveedor %s no tiene establecida\
                         la Ciudad.") % line.partner_id.name)
                ciudad_pro = self.strim_txt(line.partner_id.city, 31)
                text += ciudad_pro.upper()
                # 66 - 72 Libre
                text += 7 * ' '
            ###################################################################

            # LÍNEA 5
            ###################################################################
            if tipo_dato == '015':
                # 30 - 65 Provincia del del proveedor
                if not line.partner_id.state_id:
                    raise UserError(
                        _("Error: El Proveedor %s no tiene\
                         establecido la provincia.\
                         ") % line.partner_id.name)
                provincia = self.strim_txt(
                    line.partner_id.state_id.name, 36)
                text += provincia.upper()
                # 66 - 72 Libre

            # LÍNEA 6
            ###################################################################
            if tipo_dato == '101':
                text += self._get_linea_10X('101')
            ###################################################################

            # LÍNEA 7
            ###################################################################
            if tipo_dato == '102':
                text += self._get_linea_10X('102')
            ###################################################################

            # LINEAS 1XX
            ###################################################################
            if tipo_dato not in ['101', '102'] and tipo_dato[0] == '1':
                payment_line = trans_by_key[tipo_dato]

                # 30/31 - 39/40: Número factura
                inv_text = ''
                inv_text += self.strim_txt(payment_line.communication, 10)

                # 40 - 45 Separación
                inv_text += 6 * ' '

                invoice = payment_line.move_line_id.invoice_id
                # 46 - 53 Fecha factura
                fecha_factura = 8 * ' '
                if invoice.date_invoice:
                    fecha_factura = fields.Date.from_string(
                        invoice.date_invoice).strftime('%d-%m-%y')
                else:
                    fecha_factura = fields.Date.from_string(
                        payment_line.move_line_id.date).strftime(
                            '%d-%m-%y')
                inv_text += fecha_factura

                # 54 - 57 Separacion
                # inv_text += 4 * ' '

                # 58 - 68 Importe
                inv_text += \
                    ('%.2f' % payment_line.amount_company_currency).replace('.', ',').rjust(11)
                sep_final = 4 * ' '
                # Líneas pares desplazadas
                if int(tipo_dato) % 2 == 0:
                    inv_text = ' ' + inv_text
                    sep_final = 3 * ' '

                inv_text += sep_final

                text += inv_text

            # LÍNEA FINAL
            ###################################################################
            if tipo_dato == '910':
                # 30 - 37 Fecha vencimiento pagaré
                text += self._get_fecha_vencimiento(line)
                # 38 - 72: Libre
                text += 35 * ' '
            ###################################################################

            text = text[:72] + '\r\n'
            all_text += text
            self.num_lineas += 1
        return all_text

    def _pop_totales_pagare_caix(self, line, num_lineas):
            text = ''
            # 1 - 2: Código registro
            text += '08'
            # 3 - 4: Codigo operación
            text += '56 '

            # 5 - 14: NIF ordenante
            vat = self.convert_vat(self.company_partner_bank_id.partner_id)
            text += self.convert(vat, 9)
            # 18 - 26: Libre
            text += 15 * ' '

            # 30 - 41 Importe total
            text += self.convert(abs(self.total_company_currency), 12)

            # 42 - 49 Nº Pagarés
            num = str(self.bank_line_count)
            text += num.zfill(8)

            # 50 - 59: Nº registros
            total_reg = num_lineas + 1
            total_reg = str(total_reg)
            text += total_reg.zfill(10)

            text = text[:72] + '\r\n'
            return text
